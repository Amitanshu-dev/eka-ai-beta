import os
import sqlite3
from datetime import timedelta

from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from google import genai


app = Flask(__name__)
load_dotenv()
app.secret_key = os.getenv("SECRET_KEY")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)
def generate_ai_response(prompt):

    models = [
        "gemini-2.5-xyz",
        "gemini-2.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-3.5-flash",
    ]

    last_error = None

    for model in models:
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config={
                    "max_output_tokens": 1200,
                    "temperature": 0.6
                }
            )

            return response.text.strip()

        except Exception as e:
            print(f"{model} failed: {e}")
            last_error = e

    raise Exception(f"Sorry For inconvenience we are experiencing technical difficulties: {last_error}")

def get_db():
    conn = sqlite3.connect("eka_ai.db")
    conn.row_factory = sqlite3.Row
    return conn
def load_memory(user_email):
    conn=get_db()
    cur=conn.cursor()
    cur.execute("""
    SELECT *
    FROM lesson_memory
    WHERE user_email=?
    """,(user_email,))
    memory=cur.fetchone()
    conn.close()
    return memory
def save_memory(user_email, subject, chapter, concept, language,difficulty="Beginner",mentor_personality="Kai Sensei"):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO lesson_memory
    (
        user_email,
        subject,
        chapter,
        current_concept,
        language,
        difficulty,
        mentor_personality
    )

    VALUES(?,?,?,?,?,?,?)

    ON CONFLICT(user_email)
    DO UPDATE SET

    subject=excluded.subject,
    chapter=excluded.chapter,
    current_concept=excluded.current_concept,
    language=excluded.language,
    difficulty=excluded.difficulty,
    mentor_personality=excluded.mentor_personality,
    updated_at=CURRENT_TIMESTAMP
    """,
    (
        user_email,
        subject,
        chapter,
        concept,
        language,
        difficulty,
        mentor_personality
    ))


    conn.commit()
    conn.close()
def save_study_planner(
    user_email,
    goal,
    target_date,
    daily_hours,
    subjects,
    weak_subjects,
    roadmap
):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    INSERT OR REPLACE INTO study_planner(
        user_email,
        goal,
        target_date,
        daily_hours,
        subjects,
        weak_subjects,
        roadmap,
        current_week,
        current_day,
        study_streak,
        planner_status
    )
    VALUES(?,?,?,?,?,?,?,?,?,?,?)
    """, (
        user_email,
        goal,
        target_date,
        daily_hours,
        ",".join(subjects) if subjects else "",
        ",".join(weak_subjects) if weak_subjects else "",
        roadmap,
        1,
        1,
        0,
        "active"
    ))

    conn.commit()
    conn.close()
def load_study_planner(user_email):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM study_planner
        WHERE user_email=?
    """, (user_email,))
    planner = cur.fetchone()
    conn.close()
    if planner:
     planner = dict(planner)

     planner["subjects"] = (
        planner["subjects"].split(",")
        if planner["subjects"]
        else []
    )

     planner["weak_subjects"] = (
        planner["weak_subjects"].split(",")
        if planner["weak_subjects"]
        else []
    )

    return planner

# =======STUDY PLLANNERR ENGINNE========

from datetime import datetime


def remaining_days(target_date):

    if not target_date:
        return 0

    try:

        target = datetime.strptime(target_date, "%Y-%m-%d").date()

        today = datetime.now().date()

        days = (target - today).days

        return max(days, 0)

    except:
        return 0


def planner_progress(planner):

    if not planner:
        return 0

    total_days = remaining_days(planner["target_date"])

    current_day = planner["current_day"]

    if total_days <= 0:
        return 100

    progress = (current_day / (current_day + total_days)) * 100

    return round(progress)


def planner_summary(planner):

    if not planner:
        return None

    return {

        "goal": planner["goal"],

        "target_date": planner["target_date"],

        "daily_hours": planner["daily_hours"],

        "subjects": planner["subjects"],

        "weak_subjects": planner["weak_subjects"],

        "roadmap": planner["roadmap"],

        "week": planner["current_week"],

        "day": planner["current_day"],

        "streak": planner["study_streak"],

        "remaining_days": remaining_days(
            planner["target_date"]
        ),

        "progress": planner_progress(planner)

    }

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         email TEXT UNIQUE,
         name TEXT,
         picture TEXT
         )
    """)
    cur.execute("""
CREATE TABLE IF NOT EXISTS chats(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT,
    title TEXT,
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
    cur.execute("""
CREATE TABLE IF NOT EXISTS messages(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER,
    role TEXT,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS lesson_memory(
    user_email TEXT PRIMARY KEY,
    subject TEXT,
    chapter TEXT,
    current_concept TEXT,
    language TEXT,
    difficulty TEXT DEFAULT 'beginner',
    mentor_personality TEXT DEFAULT 'Kai Sensei',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cur.execute("""
CREATE TABLE IF NOT EXISTS study_planner(
    user_email TEXT PRIMARY KEY,

    goal TEXT,

    target_date TEXT,

    daily_hours INTEGER,

    subjects TEXT,

    weak_subjects TEXT,

    roadmap TEXT,

    current_week INTEGER DEFAULT 1,

    current_day INTEGER DEFAULT 1,

    study_streak INTEGER DEFAULT 0,

    planner_status TEXT DEFAULT 'setup'
)
""")
    try:
     cur.execute("""
    ALTER TABLE lesson_memory
    ADD COLUMN mentor_personality TEXT DEFAULT 'Kai Sensei'
    """)
    except:
     pass
    conn.commit()
    conn.close()


oauth = OAuth(app)
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile"
    }
)

init_db()


@app.route("/login")
def login():
    redirect_uri = url_for("callback", _external=True)
    print("REDIRECT URI =", redirect_uri)
    return oauth.google.authorize_redirect(redirect_uri)


@app.route("/login/callback")
def callback():
    token = oauth.google.authorize_access_token()
    user = token["userinfo"]
    session.permanent = True
    session["user"] = {
        "name": user["name"],
        "email": user["email"],
        "picture": user["picture"]
    }
    session.modified=True

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
       INSERT OR IGNORE INTO users(email,name,picture)
        VALUES(?,?,?)
        """, (
        user["email"],
        user["name"],
        user["picture"]
    ))
    conn.commit()
    conn.close()

    return redirect("/last_chat")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/")
def home():
    if "user " in session:
        return redirect("/last_chat")
    return render_template("index.html")

@app.route("/last_chat")
def last_chat():

    if "user" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id
        FROM chats
        WHERE user_email = ?
        ORDER BY id DESC
        LIMIT 1
    """, (session["user"]["email"],))

    row = cur.fetchone()

    conn.close()

    if row:
        return redirect(f"/chat/{row['id']}")

    return redirect("/new_chat")
@app.route("/new_chat")
def new_chat():
    if "user" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO chats(user_email, title)
        VALUES(?, ?)
    """, (
        session["user"]["email"],
        "New Chat"
    ))
    conn.commit()
    chat_id = cur.lastrowid
    conn.close()

    return redirect(f"/chat/{chat_id}")


@app.route("/chat/<int:chat_id>")
def chat(chat_id):
    if "user" not in session:
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT * FROM chats
        WHERE id=? AND user_email=?
    """, (
        chat_id,
        session["user"]["email"]
    ))
    chat = cur.fetchone()

    if chat is None:
        conn.close()
        return "Chat not found", 404

    cur.execute("""
        SELECT role, message
        FROM messages
        WHERE chat_id=?
        ORDER BY id
    """, (chat_id,))
    messages = cur.fetchall()

    cur.execute("""
SELECT id, title
FROM chats
WHERE user_email=?
ORDER BY created_at DESC
""", (
        session["user"]["email"],
    ))
    all_chats = cur.fetchall()
    conn.close()

    return render_template(
        "chat.html",
        chat_id=chat_id,
        messages=messages,
        all_chats=all_chats
    )


@app.route("/rename_chat", methods=["POST"])
def rename_chat():
    if "user" not in session:
        return jsonify({"success": False})

    data = request.json
    chat_id = data["chat_id"]
    new_title = data["title"]

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    UPDATE chats
    SET title=?
    WHERE id=? AND user_email=?
    """, (
        new_title,
        chat_id,
        session["user"]["email"]
    ))
    conn.commit()
    conn.close()

    return jsonify({"success": True})


@app.route("/delete_chat", methods=["POST"])
def delete_chat():
    if "user" not in session:
        return jsonify({"success": False})

    data = request.json
    chat_id = data["chat_id"]

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    DELETE FROM messages
    WHERE chat_id=?
    """, (chat_id,))
    cur.execute("""
    DELETE FROM chats
    WHERE id=? AND user_email=?
    """, (
        chat_id,
        session["user"]["email"]
    ))
    conn.commit()
    conn.close()

    return jsonify({"success": True})


user_limits = {}
MAX_DAILY_MESSAGES = 25
chat_history = {}


def generate_chat_title(first_message):
    prompt = f"""
Generate a short chat title.

Rules:
- Maximum 5 words
- Do not use quotes
- No punctuation at the end
- Use user's first message

User:
{first_message}
"""
    response = generate_ai_response(prompt)
    return response
def extract_memory(user_message, ai_response):
    prompt = f"""
Extract lesson information.

Return ONLY valid JSON.

If any field is unknown, keep previous value by returning "".

JSON format:

{{
"subject":"",
"chapter":"",
"concept":"",
"language":""
}}

User:
{user_message}

AI:
{ai_response}
"""


    response = generate_ai_response(prompt)
    import json

    try:
        text = response

        if text.startswith("```"):
            text = text.replace("```json", "").replace("```", "").strip()

        return json.loads(text)

    except:
        return None
def get_personality_prompt(personality):
  personalities = {

    "Kai Sensei": """
You are Kai Sensei.
Teach in a disciplined, clear and concept-first way.
Push the student to think.
Never spoon-feed immediately.
-RULE
Never introduce yourself again in the same chat unless the student explicitly asks who you are or changes the mentor.
When starting a brand new conversation introduce yourself like this:
Hello!
I am Kai Sensei.
I teach in a disciplined,
concept-first way.
I won't simply give answers.
I'll help you truly understand every topic.
After introducing yourself,
ask:
What would you like to learn today?
Never ask for preferred language.
""",

    "Friendly Teacher": """
Be warm, patient and encouraging.
Assume the student is a beginner.
Praise genuine progress.
-RULE
Never introduce yourself again in the same chat unless the student explicitly asks who you are or changes the mentor.
When starting a brand new conversation, introduce yourself like this:

Hi! 😊

I'm your Friendly Teacher.

Don't worry if a topic feels difficult or confusing. We'll learn it together, one small step at a time.

There are no silly questions here, and I'm always happy to explain things in a simple way.

What would you like to learn today?
""",

    "Exam Coach": """
Focus only on exams.
Teach high-weightage topics.
Give PYQ-style questions.
Keep explanations short.
-RULE
Never introduce yourself again in the same chat unless the student explicitly asks who you are or changes the mentor.
When starting a brand new conversation, introduce yourself like this:

Hello!

I am your Exam Coach.

Our goal is simple: score better with smart preparation.

We'll focus on high-weightage concepts, previous year questions, and exam-oriented practice without wasting time.

Which subject are we preparing today?
""",

    "Professor": """
Teach deeply.
Explain every concept thoroughly.
Use real-life examples.
Connect concepts together.
-RULE
Never introduce yourself again in the same chat unless the student explicitly asks who you are or changes the mentor.
When starting a brand new conversation, introduce yourself like this:

Greetings.

I am Professor.

My goal is to help you understand every topic deeply by connecting concepts, logic, and real-world applications.

We'll focus on true understanding rather than shortcuts.

Which topic shall we explore today?
""",

    "Socratic Teacher": """
Do not directly give answers.
Ask guiding questions.
Help the student discover the answer.
-RULE
Never introduce yourself again in the same chat unless the student explicitly asks who you are or changes the mentor.
When starting a brand new conversation introduce yourself like this:

Hello!

I am the Socratic Teacher.

I teach through questions,
reasoning and discovery.

Instead of giving answers immediately,
I'll guide you until you discover them yourself.

After introducing yourself ask:

What would you like to learn today?

Never ask for preferred language.
""",

    "Ruthless Mentor": """
Be strict.
Demand discipline.
Do not waste time.
Never insult or abuse the student.
Stay professional.
-RULE
Never introduce yourself again in the same chat unless the student explicitly asks who you are or changes the mentor.
When starting a brand new conversation, introduce yourself like this:

Good.

I'm the Ruthless Mentor.

I'm here to build discipline, consistency, and real understanding.

I'll challenge you to think, push you when you avoid difficult work, and keep you focused on progress—not excuses.

What are we conquering today?
"""
}
  return personalities.get(
      personality,
      personalities["Kai Sensei"])


def ask_ai(prompt, chat_id, user_id="default"):
    try:
        memory=load_memory(user_id)
        planner = load_study_planner(user_id)
        planner_data = planner_summary(planner)
        planner_context = ""
        if planner_data:
         planner_context = f"""

===== ACTIVE STUDY PLANNER =====

Goal: {planner_data['goal']}

Daily Study Time: {planner_data['daily_hours']}

Roadmap: {planner_data['roadmap']}

Current Week: {planner_data['week']}

Current Day: {planner_data['day']}

Remaining Days: {planner_data['remaining_days']}

Progress: {planner_data['progress']}%

Subjects: {planner_data['subjects']}

Weak Subjects: {planner_data['weak_subjects']}

================================

"""
        print("Planner Exists:", planner is not None)
        saved_subject=""
        saved_chapter=""
        saved_concept=""
        saved_language=""
        saved_difficulty="beginner"
        saved_personality="Kai Sensei"
        personality_prompt =(
        get_personality_prompt(saved_personality)
           )
        if memory:
           saved_subject = memory["subject"] or ""
           saved_chapter = memory["chapter"] or ""
           saved_concept = memory["current_concept"] or ""
           saved_language = memory["language"] or ""
           saved_difficulty = memory["difficulty"] or "Beginner"
           saved_personality = memory["mentor_personality"] or "Kai Sensei"
           personality_prompt =(
           get_personality_prompt(saved_personality)
           )

        if user_id not in chat_history:
            chat_history[user_id] = {
                "summary": "",
                "subject": "",
                "chapter": "",
                "current_concept": "",
                "language": "",
                "started": False,
                "chat_id": chat_id
            }
        else:
            chat_history[user_id]["chat_id"] = chat_id

        SYSTEM_PROMPT = """
You are EKA AI.
You are a personal AI teacher whose only goal is to make the student genuinely understand every topic.
IDENTITY
Introduce yourself only once in the very first conversation.
Never introduce yourself again unless the user explicitly asks who you are.
Never repeat greetings unnecessarily.
PRIMARY GOAL
Teach the student so clearly that they can solve questions without memorizing blindly.
Always focus on understanding first, marks second.
LANGUAGE RULES
Default teaching language is English.
If the student asks to change language,
immediately switch.
Never ask for preferred language unless the student requests it..
NO ASSUMPTIONS
Never assume anything.
If the user has not specified enough information, politely ask for it.
Do not invent:
Subject
Chapter
Topic
Difficulty
Exam
If information is missing, ask simple questions and wait.
TEACHING STYLE
Teach like an experienced personal teacher.
Never rush.
Teach one concept at a time.
Do not explain the whole chapter in one response.
Every response should move only one small step forward.
Always check whether the student understood before continuing.
Keep explanations short, clear and beginner friendly.
Avoid unnecessary theory.
Always explain why something works.
REAL LIFE EXAMPLES
Whenever possible:
Use daily life examples.
Especially for Physics.
Explain concepts visually using imagination.
Relate difficult ideas to real life.
MATHEMATICS RULES

Never waste time on unnecessary theory.

Teach using:

Formula

Meaning of formula

Step-by-step solving

Worked examples

Then practice questions.

All mathematical expressions must be written using proper LaTeX so they render correctly.

Rules:

- Inline mathematics must use:
  $...$

- Display equations must use:
  $$...$$

Always use proper LaTeX commands whenever applicable.

Examples:

Fractions:
$$
\frac{a+b}{c}
$$

Square roots:
$$
\sqrt{x}
$$

Powers:
$$
x^2,\;x^3
$$

Subscripts:
$$
a_1,\;x_n
$$

Integrals:
$$
\int x^2\,dx=\frac{x^3}{3}+C
$$

Derivatives:
$$
\frac{dy}{dx}
$$

Matrices:
$$
\begin{pmatrix}
1&2\\
3&4
\end{pmatrix}
$$

Greek symbols:
$$
\pi,\;\theta,\;\alpha,\;\beta,\;\lambda
$$

Summations:
$$
\sum_{i=1}^{n} i
$$

Limits:
$$
\lim_{x\to0}\frac{\sin x}{x}=1
$$

Never write mathematical equations as plain text if LaTeX can be used.

Always produce valid KaTeX-compatible LaTeX.
PHYSICS RULES
Always explain:
Meaning
Units
Formula
Why the formula works
Real-life example
Then numerical questions.
CHEMISTRY RULES
Explain reactions simply.
Explain why reactions happen.
Avoid memorization whenever possible.
FLOW
Step 1
Understand what the student wants to study.
Step 2
Teach one concept.
Step 3
Give 2–3 conceptual questions.
Step 4
Ask the student to solve them.
Step 5
Explain mistakes simply.
Step 6
Move to the next concept only after the current one is understood.
QUESTION MODE
Whenever giving practice questions:
Tell the student:
Start the study timer.
Try solving these as quickly as possible.
When finished, tell me how many minutes you took.
Do not reveal answers immediately.
Wait for the student's attempt.
If they are wrong:
Explain the mistake simply.
Show the correct thinking process.
Then solve the question step by step.
Never shame the student.
MEMORY
Remember:
Current subject
Current chapter
Current topic
Current concept
Preferred language
Continue from where the student stopped.
Do not restart unless the student asks.
If the student asks a doubt, answer it first.
Then continue from the same concept.
COMMUNICATION STYLE
Be motivating.
Be disciplined.
Be patient.
Do not be unnecessarily rude.
If the student keeps wasting time repeatedly, remind them firmly to focus.
Never insult the student.
Never use abusive language.
FORMATTING
Never use Markdown.
Never use:







Never use Markdown tables.

Never use Markdown lists.

Never use LaTeX.

Use simple plain text.

Keep paragraphs short.

Maximum 4 lines per paragraph.

Leave one blank line between paragraphs.

Output must look clean on both desktop and mobile.

END OF EVERY LESSON

After every concept:

Ask whether the student understood.

Ask if they have any doubt.

If not, tell them the name of the next concept.

Wait for their reply before continuing.

ADAPTIVE LEARNING ENGINE
Continuously judge the student's understanding from every reply.
If the student answers correctly multiple times:
Increase the difficulty gradually.
Move from basic questions to conceptual questions.
Then move to application-based questions.
Finally move to difficult questions.
Never increase difficulty suddenly.
If the student gives an incorrect answer:
Do not simply give the correct answer.
First explain why the answer is incorrect.
Then explain the concept again in a simpler way.
Use another real-life example.
Give one easier practice question.
Only continue after the student understands.
If the student repeatedly struggles with the same concept:
Assume the basics are weak.
Go one level lower and rebuild the foundation.
Never blame or insult the student.
If the student solves questions very quickly and accurately:
Offer a Challenge Question.
Tell the student:
"Excellent. Let's see if you can solve a more challenging problem."
If the student asks to skip a concept:
Politely warn them if the concept is important.
If it is a prerequisite for future concepts, recommend learning it first.
Otherwise continue.
Always adapt the teaching speed to the student's understanding.
The goal is genuine understanding, not finishing the syllabus quickly.

ACTIVE STUDY PLANNER RULES

If an active study planner exists:

Always use it as the student's primary long-term goal.

Before answering any study-related question, silently consider:

- Goal
- Current Week
- Current Day
- Remaining Days
- Progress
- Weak Subjects
- Roadmap

If the user asks something unrelated to their active study goal,
politely remind them about today's study goal before answering.

If the user asks about the subject inside their planner,
teach according to that planner.

Never ignore an active planner.

Behave like a personal mentor, not just a chatbot.

Always encourage the student to complete today's target before moving ahead.

Never invent planner data.

Only use the planner information provided in the Active Study Planner section.

"""
        SYSTEM_PROMPT += "\n\n" + planner_context
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
SELECT summary
FROM chats
WHERE id=?
""", (chat_id,))

        row = cur.fetchone()
        summary = ""

        if row and row["summary"]:
            summary = row["summary"]

        cur.execute("""
SELECT role, message
FROM messages
WHERE chat_id=?
ORDER BY id DESC
LIMIT 30
""", (chat_id,))

        rows = cur.fetchall()
        conn.close()

        rows = list(reversed(rows))
        conversation = ""

        for row in rows:
            conversation += f"{row['role'].upper()}: {row['message']}\n"

            prompt=f"""


        {SYSTEM_PROMPT}
        Current Personality
        {personality_prompt}
Subject: {saved_subject}
Chapter: {saved_chapter}
Current Concept: {saved_concept}
Language: {saved_language}
Difficulty: {saved_difficulty}
Mentor Personality: {saved_personality}
{planner_context}
        Previous Summary:
        {summary}
        Current Lesson:
Subject: {chat_history[user_id]["subject"]}
Chapter: {chat_history[user_id]["chapter"]}
Current Concept: {chat_history[user_id]["current_concept"]}
Language: {chat_history[user_id]["language"]}
         Conversation:
         {conversation}
     Reply to only the latest user message.
    """,
        response = generate_ai_response(prompt)
        return response
    except Exception as e:
        return f"AI ERROR: {str(e)}"


@app.route("/ask", methods=["POST"])
def ask():
    print("========== ASK ==========")
    print(request.json)
    data = request.json
    prompt = data.get("prompt")
    chat_id = data.get("chat_id")
    user_id = session["user"]["email"]

    if user_id not in chat_history:
        chat_history[user_id] = {
            "summary": "",
            "subject": "",
            "chapter": "",
            "current_concept": "",
            "language": "",
            "started": False,
            "chat_id": chat_id
        }

    chat_history[user_id]["chat_id"] = chat_id
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
INSERT INTO messages(chat_id, role, message)
VALUES(?, ?, ?)
""", (
        chat_id,
        "user",
        prompt
    ))
    conn.commit()
    conn.close()

    if user_id not in user_limits:
        user_limits[user_id] = 0

    if user_limits[user_id] >= MAX_DAILY_MESSAGES:
        return jsonify({
            "response": "Free limit reached. Upgrade to continue."
        })

    user_limits[user_id] += 1

    result = ask_ai(prompt, chat_id, user_id)
    memory = extract_memory(prompt, result)
    if memory:
      old = load_memory(user_id)
      save_memory(
    user_id,
    memory["subject"] if memory["subject"] else (old["subject"] if old else ""),
    memory["chapter"] if memory["chapter"] else (old["chapter"] if old else ""),
    memory["concept"] if memory["concept"] else (old["current_concept"] if old else ""),
    memory["language"] if memory["language"] else (old["language"] if old else ""),
    old["difficulty"] if old else "Beginner",
    old["mentor_personality"] if old else "Kai Sensei"
)



    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
SELECT title
FROM chats
WHERE id=?
""", (chat_id,))

    row = cur.fetchone()
    if row and row["title"] == "New Chat":
        title = generate_chat_title(prompt)
    else:
        title = row["title"]

    cur.execute("""
    UPDATE chats
    SET title=?
    WHERE id=?
    """, (
        title,
        chat_id
    ))
    cur.execute("""
INSERT INTO messages(chat_id, role, message)
VALUES(?, ?, ?)
""", (
        chat_id,
        "assistant",
        result
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "response": result
    })

@app.route("/change_personality", methods=["POST"])
def change_personality():
    print("========== CHANGE PERSONALITY ==========")
    print(request.json)
    if "user" not in session:
        return jsonify({"success": False})
    data = request.json
    personality = data.get("personality", "Kai Sensei")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
INSERT INTO lesson_memory
(
    user_email,
    mentor_personality
)
VALUES (?, ?)

ON CONFLICT(user_email)
DO UPDATE SET

mentor_personality = excluded.mentor_personality
""", (
    session["user"]["email"],
    personality
))


    conn.commit()
    if session["user"]["email"] in chat_history:
      chat_history[session["user"]["email"]]["personality"] = personality
    conn.close()

    return jsonify({"success": True})
@app.route("/save_study_planner", methods=["POST"])
def save_study_planner_route():

    if "user" not in session:
        return jsonify({"success": False})

    data = request.json

    save_study_planner(
        session["user"]["email"],
        data.get("goal"),
        data.get("target_date"),
        data.get("daily_hours"),
        data.get("subjects"),
        data.get("weak_subjects"),
        data.get("roadmap")
    )

    return jsonify({"success": True})
@app.route("/load_study_planner", methods=["GET"])
def load_study_planner_route():

    if "user" not in session:
        return jsonify({
            "success": False
        })

    planner = load_study_planner(session["user"]["email"])

    if not planner:
        return jsonify({
            "success": False
        })

    return jsonify({
        "success": True,
        "planner": {
            "goal": planner["goal"],
            "targetDate": planner["target_date"],
            "dailyTime": planner["daily_hours"],
            "subjects": planner["subjects"],
            "weakSubjects": planner["weak_subjects"],
            "roadmap": planner["roadmap"]
        }
    })
@app.route("/question_mode", methods=["POST"])
def question_mode():
    if "user" not in session:
        return jsonify({"response": "Login Required"})

    data = request.json

    subject = data.get("subject")
    topic = data.get("topic")
    difficulty = data.get("difficulty")

    prompt = f"""
You are EKA AI.

Create exactly 8 questions.

Subject: {subject}

Topic: {topic}

Difficulty: {difficulty}

Rules

- Only questions.
- No answers.
- No explanation.
- Number every question.
- Wait for student answers.

Difficulty Guide

Easy = Basic

Intermediate = Conceptual

Hard = Numerical + Application

Brutal = Toughest conceptual questions like IIT and UPSC and SSC
MATHEMATICS RULES

All mathematical expressions must be written using proper LaTeX so they render correctly.

Rules:

- Inline mathematics must use:

  $...$

- Display equations must use:

  $$...$$

Always use proper KaTeX-compatible LaTeX.

Examples:

Fractions:

$$
\frac{{a+b}}{{c}}
$$

Square roots:

$$
\sqrt{{x}}
$$

Powers:

$$
x^2,\;x^3
$$

Subscripts:

$$
a_1,\;x_n
$$

Quadratic Formula:

$$
x=\frac{{-b\pm\sqrt{{b^2-4ac}}}}{{2a}}
$$

Integrals:

$$
\int x^2\,dx=\frac{{x^3}}{{3}}+C
$$

Derivatives:

$$
\frac{{dy}}{{dx}}
$$

Matrices:

$$
\begin{{pmatrix}}
1 & 2\\
3 & 4
\end{{pmatrix}}
$$

Greek symbols:

$$
\pi,\;\theta,\;\alpha,\;\beta,\;\lambda
$$

Summations:

$$
\sum_{{i=1}}^{{n}} i
$$

Limits:

$$
\lim_{{x\to0}}\frac{{\sin x}}{{x}}=1
$$

Never write mathematical equations as plain text if LaTeX can be used.

Always produce valid KaTeX-compatible LaTeX.
"""
    

    response = client.models.generate_content
    return jsonify({
        "response": response
    })
@app.route("/exam_mode", methods=["POST"])
def exam_mode():
    if "user" not in session:
        return jsonify({"response": "Login Required"})
    
    data = request.json

    exam = data.get("exam")

    subject = data.get("subject")

    chapter = data.get("chapter")

    difficulty = data.get("difficulty")

    question_type = data.get("question_type")

    time_available = data.get("time")
    prompt = f"""
You are EKA AI.

Current Mode:
Exam Mode

Your only goal is to maximize the student's exam score.

Exam:
{exam}

Subject:
{subject}

Chapter:
{chapter}

Difficulty:
{difficulty}

Question Type:
{question_type}

Available Time:
{time_available}

RULES

Behave like an experienced exam mentor.

Do not behave like a normal AI chatbot.

Never explain the entire syllabus.

Always keep the student's exam in mind.

Never assume missing information.

If Subject is missing, ask for it and wait.

Chapter is OPTIONAL.

If Chapter is provided:

Focus only on that chapter.

If Chapter is empty:

Identify the highest-weightage chapters, most repeated concepts and frequently asked topics for the selected exam and subject.

Prepare the student accordingly.

FIRST RESPONSE

First explain your strategy in 2-3 short paragraphs.

Tell the student:

Which topics deserve the highest priority.

Which concepts are repeatedly asked.

Which mistakes students usually make.

Mention approximately which topics deserve more study time.

RAPID REVISION

Give a quick revision before asking questions.

Maximum 10 short points.

Only include important exam-oriented concepts.
MATHEMATICS RULES

Never waste time on unnecessary theory.

Teach using:

Formula

Meaning of formula

Step-by-step solving

Worked examples

Then practice questions.

All mathematical expressions must be written using proper LaTeX so they render correctly.

Rules:

- Inline mathematics must use:

  $...$

- Display equations must use:

  $$...$$

Always use proper KaTeX-compatible LaTeX.

Examples:

Fractions:

$$
\frac{{a+b}}{{c}}
$$

Square roots:

$$
\sqrt{{x}}
$$

Powers:

$$
x^2,\;x^3
$$

Subscripts:

$$
a_1,\;x_n
$$

Quadratic Formula:

$$
x=\frac{{-b\pm\sqrt{{b^2-4ac}}}}{{2a}}
$$

Integrals:

$$
\int x^2\,dx=\frac{{x^3}}{{3}}+C
$$

Derivatives:

$$
\frac{{dy}}{{dx}}
$$

Matrices:

$$
\begin{{pmatrix}}
1 & 2\\
3 & 4
\end{{pmatrix}}
$$

Greek symbols:

$$
\pi,\;\theta,\;\alpha,\;\beta,\;\lambda
$$

Summations:

$$
\sum_{{i=1}}^{{n}} i
$$

Limits:

$$
\lim_{{x\to0}}\frac{{\sin x}}{{x}}=1
$$

Never write mathematical equations as plain text if LaTeX can be used.

Always produce valid KaTeX-compatible LaTeX.

PHYSICS

Explain:

Formula

Meaning

Units

Real-life example if useful

Common exam mistakes

CHEMISTRY

Explain:

Important reactions

Concepts

Exceptions

Frequently confused points

QUESTION GENERATION

Generate questions according to Question Type.

MCQ

Generate exactly 10 MCQs.

Subjective

Generate exactly 8 descriptive questions.

Numerical

Generate exactly 8 numerical questions.

Mixed

Generate a balanced mixture of MCQs, Numerical and Subjective questions.

QUESTIONS MUST

Be exam-oriented.

Be based on commonly tested concepts.

Increase difficulty gradually.

Do not reveal answers.

TIMER

Before questions say:

Start your Study Timer.

Try to complete this within {time_available}.

Attempt every question without seeing notes.

After finishing, tell me how many minutes you took.

EVALUATION

Wait for the student's answers.

Never reveal answers before the student attempts.

For every wrong answer:

Explain why it is wrong.

Explain the correct concept.

Show the correct solving method.

Give one easier practice question if necessary.

FINAL ANALYSIS

After evaluation provide:

Total Score

Accuracy Percentage

Strong Concepts

Weak Concepts

Common Mistakes

Revision Priority

Recommended Next Topic

Motivate the student to continue.

FORMATTING

Never use Markdown.

Never use LaTeX.

Never use hashtags.

Never use code blocks.

Never use unnecessary symbols.

Keep paragraphs short.

Maximum four lines per paragraph.

Leave one blank line between sections.

Output must look clean and readable on both desktop and mobile.

If the selected exam has Previous Year Question trends available in your knowledge, prioritize concepts that have been repeatedly asked over low-priority concepts.

Always teach high-return topics before low-return topics.
"""
    response = generate_ai_response(prompt)
    if not exam:
     return jsonify({"response": "Please select an exam."})

    if not subject:
     return jsonify({"response": "Please select a subject."})

    return jsonify({
     "response": response
})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

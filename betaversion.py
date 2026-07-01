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


def get_db():
    conn = sqlite3.connect("eka_ai.db")
    conn.row_factory = sqlite3.Row
    return conn


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

    return redirect("/new_chat")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/")
def home():
    return render_template("index.html")


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
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return response.text.strip()


def ask_ai(prompt, chat_id, user_id="default"):
    try:
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
At the beginning, ask the user which language they are comfortable with.
Remember the chosen language.
Continue teaching in that language.
Only change language if the user explicitly asks.
Never switch language on your own.
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
All mathematical expressions must be readable.
Never use LaTeX.
Never use Markdown math.
Examples
x² + 5x + 6
√25 = 5
∫2x dx = x² + C
dy/dx
π ≈ 3.14159
Use Unicode whenever needed.
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

"""
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

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"""
        {SYSTEM_PROMPT}
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
            config={
                "max_output_tokens": 900,
                "temperature": 0.7
            }
        )
        return response.text
    except Exception as e:
        return f"AI ERROR: {str(e)}"


@app.route("/ask", methods=["POST"])
def ask():
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
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return jsonify({
        "response": response.text
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

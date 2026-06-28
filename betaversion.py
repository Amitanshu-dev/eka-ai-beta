# adding login continuation and various feature
import os
import sqlite3
from datetime import timedelta
from dotenv import load_dotenv
from flask import Flask, request, jsonify,render_template
from flask import session, redirect, url_for
from google import genai
from authlib.integrations.flask_client import OAuth
app=Flask(__name__)
load_dotenv()
app.secret_key=os.getenv("GOOGLE_CLIENT_SECRET")
app.config["PERMANENT_SESSION_LIFETIME"]=timedelta(days=30)
api_key=os.getenv("GEMINI_API_KEY")
client=genai.Client(api_key=api_key)
def get_db():
   conn=sqlite3.connect("eka_ai.db")
   conn.row_factory=sqlite3.Row
   return conn
def init_db():
   conn=get_db()
   cur=conn.cursor()
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
   redirect_uri=url_for("callback",_external=True)
   return oauth.google.authorize_redirect(redirect_uri)
@app.route("/login/callback")
def callback():
   token=oauth.google.authorize_access_token()
   user=token["userinfo"]
   session.permanent = True
   session["user"] = {
    "name": user["name"],
    "email": user["email"],
    "picture": user["picture"]
}
   conn=get_db()
   cur=conn.cursor()
   cur.execute("""
       INSERT OR IGNORE INTO users(email,name,picture)
        VALUES(?,?,?)
        """,(
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

    # Delete messages first
    cur.execute("""
    DELETE FROM messages
    WHERE chat_id=?
    """, (chat_id,))

    # Delete chat
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
chat_history={}
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
def ask_ai(prompt,chat_id,user_id="default"):
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
           chat_history[user_id]["chat_id"]=chat_id

        SYSTEM_PROMPT = """
You are EKA AI — a strict ruthless study mentor.
INTRODUCTION RULES
Do not inroduce your self again and again Only introduce yourself one time at the start
Always ask the user in which language he is comfortable
and start teaching in the language user says

RULES (VERY IMPORTANT):
If Subject is empty,
DO NOT choose any subject yourself.

If Chapter is empty,
DO NOT choose any chapter yourself.

If Current Concept is empty,
DO NOT invent any concept.
Instead ask the user:
1. Which subject?
2. Which chapter?
3. Then wait.
Never guess.
Never assume.
- Teach in SMALL steps (max 5-6 lines)
- If a user asks to study a chapter, NEVER explain the full chapter at ones
- Cover topic step-by-step (like chapters → parts → concepts)
- If you think user is talking about another topic instead of study roast them in the brutal way possible

FLOW:
1. Start from basics
2. Teach ONE concept
3. Give 2-3 short questions
4. At the end of each concept five the user next concept name and ask him to start that new concept
4. Ask user to answer or say "next"
5. WAIT for user reply
6. Then continue next concept

IMPORTANT:
- Never jump ahead
- Never skip concepts
- Never dump full chapter
- Complete topic gradually across multiple messages

STYLE:
- Hinglish allowed
- Very simple language
- Real-life examples
- Interactive teaching
LESSON MEMORY RULES
- Remember the current subject.
- Remember the current chapter.
- Remember the current concept.
- If user says "next", continue from current_concept.
- Never restart the chapter unless the user asks.
- If user asks a doubt, answer it and then continue from the same concept.
- If the chapter finishes, automatically start revision and then MCQs.
OUTPUT FORMATTING RULES (VERY IMPORTANT)
- Never use Markdown.
- Never use **bold**
- Never use *italic*
- Never use #
- Never use >
- Never use bullet markdown like -
- Never use ``` code blocks.
- Never use LaTeX ($...$, \frac, \int, \sqrt etc.)

Instead use plain text.

For maths use Unicode.

Examples

∫2x dx = x² + C

√16 = 4

π ≈ 3.14159

Use short paragraphs.

Maximum 4 lines per paragraph.

Leave one blank line between paragraphs.

Output should be beautiful on mobile.
"""
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
SELECT summary
FROM chats
WHERE id=?
""",(chat_id,))

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
            "max_output_tokens": 300,
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
    user_id=session["user"]["email"]
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
    chat_history[user_id]["chat_id"]=chat_id
    
  
# Save user message
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
# AI Response



    # init user
    if user_id not in user_limits:
        user_limits[user_id] = 0

    # check limit
    if user_limits[user_id] >=MAX_DAILY_MESSAGES:
        return jsonify({
            "response": "Free limit reached. Upgrade to continue."
        })

    user_limits[user_id] += 1

    result = ask_ai(prompt,chat_id,user_id)
    conn=get_db()
    cur=conn.cursor()
    cur.execute("""
SELECT title
FROM chats
WHERE id=?
""", (chat_id,))

    row = cur.fetchone()
    if row and row["title"] == "New Chat":
      title = generate_chat_title(prompt)
    else:
       title=row["title"]

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
   
import os
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
def teach_ai(subject, topic):
    prompt = f"""
    Explain {topic} of {subject} in very simple way like teaching a beginner student.

    Rules:
    - use simple language
    - give real life example
    - no complex theory
    - cover full topic (try to explain it breifly with a example)
    """

    response = ask_ai(prompt)

    print("\n=====EXPLAINATION=====")
    print(f"{subject.upper()} - {topic}")
    print(response)
    print("======================\n") 
def gen_questions(subject,topic):
   prompt=f"""
   create 8 conceptual questions on {topic} of {subject}.
   Rules
   -not direct theory
   -force thinking
   -no MCQ
   -short but tricky
   """
   response=ask_ai(prompt)
   print("\n---QUESTIONS---")
   print(response)
def evaluate_answer(subject, topic, question, answer):
    prompt = f"""
    Subject: {subject}
    Topic: {topic}

    Question: {question}
    Student Answer: {answer}

    Evaluate:
    - correct or wrong
    - explain mistake simply
    - give correct answer shortly
    """

    result = ask_ai(prompt)

    print("\n===== FEEDBACK =====")
    print(result)
def teach_questions(subject,topic,level):
   prompt=f"""
   topic:{topic}({subject})
   Do thease things
   Explain
   - use  simple language
    - give real life example
    - no complex theory
    - cover full topic (try to explain it breifly with a example)
   Give 8 questions bsed on level:{level}
   3 easy
   3 medium
   2 hard
    """
   response=ask_ai(prompt)
   print("\n---concept---")
   print(response)
   print("----\n")
def question_mode(study_topic,level):
   prompt=f"""
   create 8 questions on {study_topic}
   level:{level}
   Rules:
   -beginner=easy
   -intermidite=medium
   -hard=conceptual and tricky
   -Do not explain answers
   """
   response=ask_ai(prompt)
   print("\n---QUESTION MODE---")
   print(f"{study_topic.upper()}({level})")
   print(response)
   questions=response.split("\n")
   return questions
# def basic_input():
#     user_prompt = input("Bhai aaj kya padhne ka plan hai?\n>> ")

#     ai_response = ask_ai(f"""
#     User said: {user_prompt}

#     Extract:
#     - subject name (correct spelling)
#     - topic (fix spelling mistakes)
#     - hours

#     Return ONLY valid JSON.
#     No expaination
#     No text.
#     Only JSON array.
#     [
#       {{"name":"physics","topic":"transistor","hours":2}},
#       {{"name":"maths","topic":"determinant","hours":1}}
#     ]
#     """)
#     ai_response = ai_response.strip()
#     if ai_response.startswith("```"):
#      ai_response = ai_response.replace("```json", "").replace("```", "").strip()
#      import json
#     try:
#      start = ai_response.find("[")
#      end = ai_response.rfind("]") + 1
#      clean_json = ai_response[start:end]

#      subjects = json.loads(clean_json)
#     except Exception as e:
#       print("AI ne galat JSON diya:", ai_response)
#       return basic_input()

#     goals = []
#     for sub in subjects:
#         minutes = int(sub["hours"] * 60)
#         goals.append({
#             "name":sub["name"] + " - " + sub["topic"],
#             "topic":sub["topic"],
#             "hours": sub["hours"],
#             "minute": minutes,
#             "remaining": minutes
#         })
#     # simple default
#     slot_size = 30
#     break_size = 5

#     return goals, slot_size, break_size
def scheduler_engine(goals,windows,slot_size,break_size):
 schedule=[]
 goal_index=0
 for each in windows:
    current_time=each[0]
    time_left=each[1]
    while time_left>0:
      if all(g["remaining"]==0 for g in goals):
        break
      current_subject=goals[goal_index]
      if current_subject["remaining"]==0:
           goal_index=(goal_index+1)%len(goals)
           continue
      min_study_time=10
      if time_left<min_study_time:
        break
      study_time=min(current_subject["remaining"],time_left,slot_size)
      if study_time==0:
            goal_index=(goal_index+1)%len(goals)
            continue
      start_time=current_time
      end_time=current_time+study_time
      schedule_printer=(start_time,end_time,"study",current_subject["name"],current_subject["topic"])
      schedule.append(schedule_printer)
      current_subject["remaining"]=current_subject["remaining"]-study_time
      if current_subject["remaining"]<=0:
          current_subject["remaining"]=0
      time_left=time_left-study_time
      current_time=end_time
      goal_index=max(range(len(goals)),key=lambda i:goals[i]["remaining"])
      start_time=current_time
      end_time=current_time+break_size
      if time_left >= break_size:
         start_time = current_time
         end_time = current_time + break_size
         break_printer = (start_time, end_time, "break", None,None)
         schedule.append(break_printer)
         current_time += break_size
         time_left -= break_size
 return schedule
def print_schedule_engine_break_engine(schedule):
    session_count = 1
    for start_time, end_time, type, subject, topic in schedule:
        duration = int(end_time - start_time)

        if type == "study":
            print(f"Session {session_count}: {subject.upper()} - {duration} min")
            session_count += 1
        else:
            print("break 5 min")
import os
import json
total_studied=0
short_count=0
# if os.path.exists("data.json"):
#   while True:
#    choice=input("START STUDYING NOW (yes/no)->").strip().lower()
#    if choice=="yes":
#     break
#    elif choice=="no":
#     exit()
#    else:
#     print("type yes or no")
#   file=open("data.json","r")
#   data_loaded=json.load(file)
#   history=data_loaded.get("history",[])

#   progress_index=data_loaded["progress_index"]
#   remaining_time=data_loaded["remaining_time"]
#   file.close()
#   goals=data_loaded["goals"]
#   windows=[tuple(w) for w in data_loaded["windows"]]
#   schedule=[tuple(s) for s in data_loaded["schedule"]]
#   while progress_index<len(schedule):
#      current_task=schedule[progress_index]
#      start_time,end_time,type,subject,topic=current_task
#      mode = input("""
# Mode choose kar:
# 1. Study Mode (Teach + Questions) type 1
# 2. Question Mode (Only Questions) type 2
# >> """).strip()
#      if mode == "1":
#       teach_questions(subject, topic)
#       gen_questions(subject,topic)
#      elif mode == "2":
#       study_topic = input("Kaunsa topic practice karna hai?\n>> ")
#       level = input("""
# Level choose kar:
# 1. Beginner
# 2. Intermediate
# 3. Hard
# >> """).strip()
#       if level == "1":
#         level_type = "beginner"
#       elif level == "2":
#         level_type = "intermediate"
#       else:
#         level_type = "hard"
#       questions = question_mode(topic, level_type)
#       for q in questions:
#         if q.strip() == "":
#          continue
#         print("\n", q)
#         user_answer = input("Answer (ya 'skip'):\n>> ")
#         if user_answer.lower() == "skip":
#             explanation = ask_ai(f"Explain simply: {q}")
#             print("\nEXPLANATION:")
#             print(explanation)
#             continue
#         evaluate_answer("general", topic, q, user_answer)
#      if type == "study":
#       start_allowed_words=["start","begin","start karte hai","let's go","GO"]
#       import time
#       while True:
#        start=input("TYPE START TO START THE SESSION->").strip().lower()
#        if start in start_allowed_words:
#         start_real=time.time()
#         break
#        else:
#         print("Invalid input type 'start' when ready")
#       print("STARTING:", subject, "-", topic)
#       level = input("""
#        Level choose kar:
#        1. Beginner
#        2. Intermediate
#        3. Hard
#        4. Mixed (easy + medium + hard)
#        >> """).strip()
#       if level == "1":
#        level_type = "beginner"
#       elif level == "2":
#        level_type = "intermediate"
#       elif level == "3":
#         level_type = "hard"
#       elif level == "4":
#        level_type = "mixed"
#       else:
#        level_type = "mixed"
#        teach_questions(subject, topic,level_type)
#       user_answer = input("Answer karo:\n>> ")
#       evaluate_answer(subject, topic, "question", user_answer)
#      while True:
#       doubt = input("Koi doubt hai? (type 'no' to continue):\n>> ")
#       if doubt.lower() in ["no","n","abhi nahi","samajh aa gaya","clear","all clear"]:
#         print("GOOD. CONTINUE LEARNING")
#         break
#       else:
#        doubt_response = ask_ai(f""" explain simply:{doubt}
#      STRICT RULES
#      -make sure user can understand in 1st attempt
#      -elaborate your points give simple example
#      """)
#        print(doubt_response)
#      allowed_stop_words=["stop","done","end","stp","ho gaya","finish"]
#      while True:
#         stop=input("TYPE STOP WHEN DONE->").strip().lower()
#         if stop in allowed_stop_words:
#          end_real=time.time()
#          break
#         else:
#          print("Invalid input type 'stop' when done")
#      actual_time=(end_real-start_real)/60
#      print(f"session time:{round(actual_time,2)}minutes")
#      for g in goals:
#         if g["name"] == subject:
#             topic = g.get("topic", "")
#             break 
#      if type=="break":
#        progress_index+=1
#        continue
#      if remaining_time>0:
#        planned_time=remaining_time
#      else:
#        planned_time=(end_time-start_time)
#     #  print("STARTING:",subject,"DURATION:",planned_time,"Minutes Left")
#      if actual_time<1:
#         print("Session too short.Atleast try to study few minutes")
#         short_count+=1
#         if short_count>=3:
#            lock_time=600
#            print("SYSTEM: 3 failed attempts detected")
#            print("ACTION: take a 10 min break and restart seriously or else you will be a failure")
#            print(f"system locked for {lock_time//60} minutes") 
#            time.sleep(lock_time)
#            exit()
#         while True:
#          continue_study=input("continue study (yes/no)->").strip().lower()
#          if continue_study=="yes":
#           break
#          elif continue_study=="no":
#           exit()
#          else:
#           print("type yes or no only")
#      if actual_time>=planned_time:
#       print("GOOD JOB TASK COMPLTED")
#       progress_index+=1
#       remaining_time=0

#       ratio=actual_time/planned_time
#       if ratio<0.3:
#         label="failed"
#       elif ratio<0.8:
#         label="partial"
#       elif ratio<=1.2:
#         label="completed"
#       else:
#         label="overperformed"

#       sessions={
#         "subject":subject,
#         "planned_time":planned_time,
#         "actual_time":actual_time,
#         "ratio":ratio,
#         "label":label
#     }

#      if actual_time>=5:
#         history.append(sessions)
#      else:
#         print("session too short.Not counted")

#     # -------- ANALYSIS --------
#      recent_sessions=history[-5:]
#      failed=0
#      partial=0
#      completed=0

#      for each in recent_sessions:
#         if each["label"]=="failed":
#             failed+=1
#         elif each["label"]=="partial":
#             partial+=1
#         elif each["label"]=="completed":
#             completed+=1

#      if failed>partial and failed>completed:
#         user_type="lazy"
#      elif partial>failed and partial>completed:
#         user_type="inconsistent"
#      elif completed>failed and completed>partial:
#         user_type="disciplined"
#      else:
#         user_type="mixed"

#      total=failed+partial+completed
#      if total>0:
#         failed_ratio=failed/total
#      else:
#         failed_ratio=0

#     # -------- SUGGESTION --------
#      if user_type == "lazy":
#         suggestion = "Tu start hi nahi kar raha. Slot size chhota kar aur 25 min se start kar."
#      elif user_type == "inconsistent":
#         suggestion = "Tu start karta hai but finish nahi karta. Distractions hata aur focus improve kar."
#      elif user_type == "disciplined":
#         suggestion = "Tu disciplined hai. Ab difficulty badha aur zyada subjects add kar."
#      else:
#         suggestion = "Tu kabhi acha kabhi bekaar. Consistency build kar, daily minimum target fix kar."

#      if failed_ratio>0.5:
#         suggestion+="tu 50% Se jyada jyada fail kar raha hai serious ho ja"

#      if len(history)>=5:
#         print("user_type:",user_type)
#         print("suggestion:",suggestion)

#     # -------- ADAPTIVE --------
#      subjects_stats={}
#      for each in history:
#         sub=each["subject"]
#         label=each["label"]

#         if sub not in subjects_stats:
#             subjects_stats[sub]={"failed":0,"partial":0,"completed":0}

#         subjects_stats[sub][label]+=1

#      weak_subjects=[]
#      for sub in subjects_stats:
#         if subjects_stats[sub]["failed"]>subjects_stats[sub]["completed"]:
#             weak_subjects.append(sub)

#      if len(weak_subjects)>0:
#         print("weak subject detected:",weak_subjects)
#      else:
#         print("all subjects stable")

#      for i in range(len(schedule)):
#         start, end, type, subject = schedule[i]
#         if subject in weak_subjects:
#             new_end = end + 15
#             schedule[i] = (start, new_end, type, subject)

#      if weak_subjects:
#         print("AI Scheduler: Weak subjects ko boost diya gaya hai")
#      else:
#         print("AI Scheduler: Schedule optimized")
#   else:
#     remaining_time = round(planned_time - actual_time, 1)
#     ratio = actual_time / planned_time
#     if ratio < 0.3:
#         label = "failed"
#     elif ratio < 0.8:
#         label = "partial"
#     elif ratio <= 1.2:
#         label = "completed"
#     else:
#         label = "overperformed"

#     sessions = {
#         "subject": subject,
#         "planned_time": planned_time,
#         "actual_time": actual_time,
#         "ratio": ratio,
#         "label": label
#     }

#     if actual_time >= 5:
#         history.append(sessions)
#     else:
#         print("session too short.Not counted")

#     # -------- ANALYSIS --------
#     recent_sessions = history[-5:]
#     failed = 0
#     partial = 0
#     completed = 0

#     for each in recent_sessions:
#         if each["label"] == "failed":
#             failed += 1
#         elif each["label"] == "partial":
#             partial += 1
#         elif each["label"] == "completed":
#             completed += 1

#     if failed > partial and failed > completed:
#         user_type = "lazy"
#     elif partial > failed and partial > completed:
#         user_type = "inconsistent"
#     elif completed > failed and completed > partial:
#         user_type = "disciplined"
#     else:
#         user_type = "mixed"

#     total = failed + partial + completed
#     if total > 0:
#         failed_ratio = failed / total
#     else:
#         failed_ratio = 0

#     # -------- SUGGESTION --------
#     if user_type == "lazy":
#         suggestion = "Tu start hi nahi kar raha. Slot size chhota kar aur 25 min se start kar."
#     elif user_type == "inconsistent":
#         suggestion = "Tu start karta hai but finish nahi karta. Distractions hata aur focus improve kar."
#     elif user_type == "disciplined":
#         suggestion = "Tu disciplined hai. Ab difficulty badha aur zyada subjects add kar."
#     else:
#         suggestion = "Tu kabhi acha kabhi bekaar. Consistency build kar, daily minimum target fix kar."

#     if failed_ratio > 0.5:
#         suggestion += "tu 50% Se jyada fail kar raha hai serious ho ja"

#     if len(history) >= 5:
#         try:
#          ai_prompt = f"""
#          User study data:
#          User type: {user_type}
#          Failed ratio: {failed_ratio}
#          Weak subjects: {weak_subjects}
#          Give strict but helpful advice to improve discipline and study performance.
#           """
#          ai_response = ask_ai(ai_prompt)
#          if ai_response:
#           print("\n AI MENTOR:")
#           print(ai_response)
#          else:
#             print("\nAI Mentor: NO RESPONSE")
#         except Exception as e:
#            print("\nAI error:",e)

#     # -------- ADAPTIVE --------
#     subjects_stats = {}
#     for each in history:
#         sub = each["subject"]
#         label = each["label"]

#         if sub not in subjects_stats:
#             subjects_stats[sub] = {"failed": 0, "partial": 0, "completed": 0}

#         subjects_stats[sub][label] += 1

#     weak_subjects = []
#     for sub in subjects_stats:
#         if subjects_stats[sub]["failed"] > subjects_stats[sub]["completed"]:
#             weak_subjects.append(sub)

#     if len(weak_subjects) > 0:
#         print("weak subject detected:", weak_subjects)
#     else:
#         print("all subjects stable")

#     for i in range(len(schedule)):
#         start, end, type, subject = schedule[i]
#         if subject in weak_subjects:
#             new_end = end + 15
#             schedule[i] = (start, new_end, type, subject)

#     if weak_subjects:
#         print("AI Scheduler: Weak subjects ko boost diya gaya hai")
#     else:
#         print("AI Scheduler: Schedule optimized")

#     # -------- SAVE + EXIT --------
#     data = {
#         "goals": goals,
#         "windows": windows,
#         "schedule": schedule,
#         "progress_index": progress_index,
#         "remaining_time": remaining_time,
#         "history": history,
#     }

#     file = open("data.json", "w")
#     json.dump(data, file)
#     file.close()
#     print("studied:", round(actual_time, 1), "minutes") 
#     # ====== MASTER AI VALIDATION ======

#   if subject is None or planned_time <= 0:
#     print("ERROR: Invalid session data")

#   elif actual_time <= 0:
#     print("ERROR: Timer failed")

#   elif "label" not in sessions:
#     print("ERROR: Label not assigned")

#   elif sessions["label"] not in ["failed","partial","completed","overperformed"]:
#     print("ERROR: Wrong label value")

#   elif len(history) == 0:
#     print("WARNING: History empty")

#   elif len(history) >= 1:
#     print("AI CHECK: History working")

#   if len(history) >= 5:
#     print("AI CHECK: Enough data for analysis")

#     if user_type not in ["lazy","inconsistent","disciplined","mixed"]:
#         print("ERROR: user_type broken")

#     if "suggestion" not in locals():
#         print("ERROR: suggestion not generated")

#     if not isinstance(subjects_stats, dict):
#         print("ERROR: subjects_stats broken")

#     if not isinstance(weak_subjects, list):
#         print("ERROR: weak_subjects broken")

#     print("AI SYSTEM: FULLY ACTIVE")
#   else:
#     print("AI SYSTEM: LEARNING PHASE")
# else:
#     print("CREATING NEW SCHEDULE...")
#     goals,slot_size,break_size=basic_input()
#     choice=input("schedule print karu? yes or no->").strip().lower()
#     if choice=="yes":
#        total_time=sum(g["minute"]for g in goals)
#        windows=[(0,total_time)]
#        schedule=scheduler_engine(goals,windows,slot_size,break_size)
#     print("\n====TODAY'S SCHEDULE====")
#     print_schedule_engine_break_engine(schedule)

#     windows=[list(w)for w in windows]
#     schedule=[list(s)for s in schedule]

#     data={
#         "goals":goals,
#         "windows":windows,
#         "schedule":schedule,
#         "progress_index":0,
#         "remaining_time":0
#     }

#     file=open("data.json","w")
#     json.dump(data,file)
#     file.close()

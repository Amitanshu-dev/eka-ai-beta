import os
import json
import sqlite3
from datetime import timedelta, datetime

from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for,send_from_directory
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
@app.route("/robots.txt")
def robots():
    return send_from_directory("static", "robots.txt")
@app.route("/sitemap.xml")
def sitemap():
    return send_from_directory("static", "sitemap.xml")
@app.route("/googlec11108631eacbc28.html")
def google_verify():
    return send_from_directory("static", "googlec11108631eacbc28.html")
def generate_ai_response(prompt):

    models = [
        "gemini-2.5-flash",
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
    INSERT INTO study_planner(
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
    ON CONFLICT(user_email) DO UPDATE SET
        goal=excluded.goal,
        target_date=excluded.target_date,
        daily_hours=excluded.daily_hours,
        subjects=excluded.subjects,
        weak_subjects=excluded.weak_subjects,
        roadmap=excluded.roadmap,
        planner_status='active'
    """, (
        user_email,
        goal,
        target_date,
        daily_hours,
        ",".join(subjects) if subjects else "",
        ",".join(weak_subjects) if weak_subjects else "",
        json.dumps(roadmap) if isinstance(roadmap, dict) else (roadmap or ""),
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
    cur.execute("""
    CREATE TABLE IF NOT EXISTS goals(
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_email TEXT NOT NULL,

    goal_name TEXT NOT NULL,

    description TEXT DEFAULT '',

    category TEXT DEFAULT 'Study',

    priority TEXT DEFAULT 'Medium',

    target_date TEXT,

    daily_hours INTEGER DEFAULT 2,

    roadmap TEXT,

    subjects TEXT,

    weak_subjects TEXT,

    xp INTEGER DEFAULT 0,

    level INTEGER DEFAULT 1,

    streak INTEGER DEFAULT 0,

    status TEXT DEFAULT 'active',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tasks(

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    goal_id INTEGER,

    title TEXT,

    description TEXT,

    estimated_minutes INTEGER DEFAULT 30,
    
    priority TEXT DEFAULT 'Medium',

    xp_reward INTEGER DEFAULT 10,

    status TEXT DEFAULT 'pending',

    due_date TEXT,
    
    completed_at TIMESTAMP,

    task_order INTEGER DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS study_sessions(

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    goal_id INTEGER,

    study_date TEXT,

    minutes INTEGER,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS notes(

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    goal_id INTEGER,

    title TEXT,

    content TEXT,

    note_type TEXT DEFAULT 'full',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS goal_stats(

    goal_id INTEGER PRIMARY KEY,

    completed_tasks INTEGER DEFAULT 0,

    pending_tasks INTEGER DEFAULT 0,

    study_hours INTEGER DEFAULT 0,

    total_xp INTEGER DEFAULT 0,

    current_level INTEGER DEFAULT 1,

    streak INTEGER DEFAULT 0
)
""")
    try:
     cur.execute("""
    ALTER TABLE lesson_memory
    ADD COLUMN mentor_personality TEXT DEFAULT 'Kai Sensei'
    """)
    except:
     pass
    for column, definition in [
        ("current_task_id", "INTEGER"),
        ("last_completed_task", "TEXT"),
        ("weak_topics", "TEXT DEFAULT ''"),
        ("strong_topics", "TEXT DEFAULT ''"),
        ("revision_history", "TEXT DEFAULT ''"),
        ("last_study_date", "TEXT")
    ]:
        try:
            cur.execute("ALTER TABLE lesson_memory ADD COLUMN %s %s" % (column, definition))
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()
def create_goal(
     user_email,
     goal_name,
     description="",
     category="Study",
     priority="Medium",
     target_date=None,
     daily_hours=2,
     roadmap="",
     subjects="",
     weak_subjects=""        
):
    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("""
        INSERT INTO goals(
            user_email,
            goal_name,
            description,
            category,
            priority,
            target_date,
            daily_hours,
            roadmap,
            subjects,
            weak_subjects
        )
        VALUES(?,?,?,?,?,?,?,?,?,?)
        """, (
            user_email,
            goal_name,
            description,
            category,
            priority,
            target_date,
            daily_hours,
            roadmap,
            subjects,
            weak_subjects
        ))
        goal_id = cur.lastrowid

        cur.execute("""
INSERT INTO goal_stats(goal_id)
VALUES(?)
""", (goal_id,))

        conn.commit()
        return goal_id
    except Exception as e:
        print(f"Create Goal Error: {e}")
        return None
    finally:
        conn.close()
def get_all_goals(user_email):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
        SELECT *
        FROM goals
        WHERE user_email = ?
        AND status = 'active'
        ORDER BY created_at DESC
        """, (user_email,))
        goals = cur.fetchall()
        return goals
    except Exception as e:
        print(f"Get Goals Error: {e}")
        return []
    finally:
        conn.close()
def get_goal(goal_id):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
        SELECT *
        FROM goals
        WHERE id = ?
        """, (goal_id,))
        goal = cur.fetchone()
        return goal
    except Exception as e:
        print(f"Get Goal Error: {e}")
        return None
    finally:
        conn.close()
def update_goal(
    goal_id,
    goal_name,
    description,
    category,
    priority,
    target_date,
    daily_hours,
    roadmap,
    subjects,
    weak_subjects
):

    conn = get_db()
    cur = conn.cursor()

    try:

        cur.execute("""
        UPDATE goals
        SET
            goal_name = ?,
            description = ?,
            category = ?,
            priority = ?,
            target_date = ?,
            daily_hours = ?,
            roadmap = ?,
            subjects = ?,
            weak_subjects = ?
        WHERE id = ?
        """, (
            goal_name,
            description,
            category,
            priority,
            target_date,
            daily_hours,
            roadmap,
            subjects,
            weak_subjects,
            goal_id
        ))

        conn.commit()

        return True

    except Exception as e:
        print(f"Update Goal Error: {e}")
        return False

    finally:
        conn.close()
def archive_goal(goal_id):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
        UPDATE goals
        SET status = 'archived'
        WHERE id = ?
        """, (goal_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Archive Goal Error: {e}")
        return False
    finally:
        conn.close()
def delete_goal(goal_id):

    conn = get_db()
    cur = conn.cursor()

    try:

        # Delete study sessions
        cur.execute("""
        DELETE FROM study_sessions
        WHERE goal_id = ?
        """, (goal_id,))

        # Delete notes
        cur.execute("""
        DELETE FROM notes
        WHERE goal_id = ?
        """, (goal_id,))

        # Delete tasks
        cur.execute("""
        DELETE FROM tasks
        WHERE goal_id = ?
        """, (goal_id,))

        # Delete goal stats
        cur.execute("""
        DELETE FROM goal_stats
        WHERE goal_id = ?
        """, (goal_id,))

        # Finally delete goal
        cur.execute("""
        DELETE FROM goals
        WHERE id = ?
        """, (goal_id,))

        conn.commit()

        return True

    except Exception as e:

        print(f"Delete Goal Error: {e}")
        return False

    finally:

        conn.close()

def create_task(
    goal_id,
    title,
    description="",
    estimated_minutes=30,
    due_date=None
):

    conn = get_db()
    cur = conn.cursor()

    try:

        cur.execute("""
        INSERT INTO tasks(
            goal_id,
            title,
            description,
            estimated_minutes,
            due_date
        )
        VALUES(?,?,?,?,?)
        """, (
            goal_id,
            title,
            description,
            estimated_minutes,
            due_date
        ))

        conn.commit()

        return cur.lastrowid

    except Exception as e:

        print(f"Create Task Error: {e}")
        return None

    finally:

        conn.close()
def get_tasks(goal_id):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
        SELECT *
        FROM tasks
        WHERE goal_id = ?
        ORDER BY task_order ASC, due_date ASC
        """, (goal_id,))
        tasks = cur.fetchall()
        return tasks
    except Exception as e:
        print(f"Get Tasks Error: {e}")
        return []
    finally:
        conn.close()

def get_current_task(goal_id):
    """The first unfinished roadmap task is always the active daily task."""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
        SELECT * FROM tasks
        WHERE goal_id=? AND status='pending'
        ORDER BY task_order ASC, id ASC
        LIMIT 1
        """, (goal_id,))
        return cur.fetchone()
    finally:
        conn.close()

def get_active_goal(user_email):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
        SELECT * FROM goals
        WHERE user_email=? AND status='active' AND roadmap IS NOT NULL AND roadmap!=''
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """, (user_email,))
        return cur.fetchone()
    finally:
        conn.close()

def sync_planner_position(user_email, goal_id):
    task = get_current_task(goal_id)
    if not task:
        return None
    conn = get_db()
    cur = conn.cursor()
    try:
        # Roadmap task descriptions retain their generated month/week label.
        week = 1
        marker = "Week "
        description = task["description"] or ""
        if marker in description:
            try:
                week = int(description.split(marker, 1)[1].split()[0].strip(" :,-"))
            except (ValueError, IndexError):
                pass
        cur.execute("""
        UPDATE study_planner
        SET current_week=?, current_day=?
        WHERE user_email=?
        """, (week, task["task_order"] or 1, user_email))
        conn.commit()
    finally:
        conn.close()
    return task

def skip_current_task(goal_id):
    """Move forward without awarding completion XP when the learner skips."""
    task = get_current_task(goal_id)
    if not task:
        return None
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE tasks SET status='skipped' WHERE id=?", (task["id"],))
        conn.commit()
    finally:
        conn.close()
    return get_current_task(goal_id)

def sync_learning_memory(user_email, goal, task, last_completed_task=None, user_message=""):
    """Keep cross-chat learning state in the existing per-user memory record."""
    if not goal:
        return
    conn = get_db()
    cur = conn.cursor()
    try:
        current_title = task["title"] if task else ""
        cur.execute("""
        INSERT INTO lesson_memory(
            user_email, subject, chapter, current_concept, current_task_id,
            last_completed_task, last_study_date
        ) VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(user_email) DO UPDATE SET
            subject=excluded.subject,
            chapter=excluded.chapter,
            current_concept=excluded.current_concept,
            current_task_id=excluded.current_task_id,
            last_completed_task=COALESCE(excluded.last_completed_task, lesson_memory.last_completed_task),
            last_study_date=excluded.last_study_date,
            updated_at=CURRENT_TIMESTAMP
        """, (
            user_email, goal["goal_name"], current_title, current_title,
            task["id"] if task else None, last_completed_task,
            datetime.now().strftime("%Y-%m-%d")
        ))
        message = (user_message or "").lower()
        if current_title and any(word in message for word in ("confused", "don't understand", "dont understand", "difficult", "wrong")):
            cur.execute("""
            UPDATE lesson_memory SET weak_topics=CASE
                WHEN instr(weak_topics, ?) > 0 THEN weak_topics
                WHEN weak_topics='' THEN ? ELSE weak_topics || ', ' || ? END
            WHERE user_email=?
            """, (current_title, current_title, current_title, user_email))
        elif current_title and any(word in message for word in ("understood", "easy", "got it", "correct")):
            cur.execute("""
            UPDATE lesson_memory SET strong_topics=CASE
                WHEN instr(strong_topics, ?) > 0 THEN strong_topics
                WHEN strong_topics='' THEN ? ELSE strong_topics || ', ' || ? END
            WHERE user_email=?
            """, (current_title, current_title, current_title, user_email))
        if current_title and ("revision" in message or "revise" in message):
            cur.execute("""
            UPDATE lesson_memory SET revision_history=CASE
                WHEN revision_history='' THEN ? ELSE revision_history || ', ' || ? END
            WHERE user_email=?
            """, (current_title, current_title, user_email))
        conn.commit()
    finally:
        conn.close()
def get_task(task_id):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
        SELECT *
        FROM tasks
        WHERE id = ?
        """, (task_id,))
        task = cur.fetchone()
        return task
    except Exception as e:
        print(f"Get Task Error: {e}")
        return None
    finally:
        conn.close()
def update_task(
    task_id,
    title,
    description,
    estimated_minutes,
    due_date
):

    conn = get_db()
    cur = conn.cursor()

    try:

        cur.execute("""
        UPDATE tasks
        SET
            title = ?,
            description = ?,
            estimated_minutes = ?,
            due_date = ?
        WHERE id = ?
        """, (
            title,
            description,
            estimated_minutes,
            due_date,
            task_id
        ))

        conn.commit()

        return True

    except Exception as e:

        print(f"Update Task Error: {e}")

        return False

    finally:

        conn.close()
from datetime import datetime

def complete_task(task_id):

    conn = get_db()
    cur = conn.cursor()

    try:

        # Task ki details lo
        cur.execute("""
        SELECT goal_id, xp_reward, status
        FROM tasks
        WHERE id = ?
        """, (task_id,))

        task = cur.fetchone()

        if not task:
            return False

        if task["status"] == "completed":
            return True

        goal_id = task["goal_id"]
        xp_reward = task["xp_reward"]

        # Task complete karo
        cur.execute("""
        UPDATE tasks
        SET
            status = 'completed',
            completed_at = ?
        WHERE id = ?
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            task_id
        ))

        # Goal XP update
        cur.execute("""
        UPDATE goals
        SET xp = xp + ?
        WHERE id = ?
        """, (
            xp_reward,
            goal_id
        ))

        # Goal stats update
        cur.execute("""
        UPDATE goal_stats
        SET
            completed_tasks = completed_tasks + 1,
            pending_tasks = pending_tasks - 1,
            total_xp = total_xp + ?
        WHERE goal_id = ?
        """, (
            xp_reward,
            goal_id
        ))

        conn.commit()

        return True

    except Exception as e:

        print(f"Complete Task Error: {e}")
        return False

    finally:

        conn.close()
def delete_task(task_id):

    conn = get_db()
    cur = conn.cursor()

    try:

        # Goal ID aur status nikaalo
        cur.execute("""
        SELECT goal_id, status
        FROM tasks
        WHERE id = ?
        """, (task_id,))

        task = cur.fetchone()

        if not task:
            return False

        goal_id = task["goal_id"]
        status = task["status"]

        # Task delete karo
        cur.execute("""
        DELETE FROM tasks
        WHERE id = ?
        """, (task_id,))

        # Agar task pending tha to pending count ghatao
        if status == "pending":
            cur.execute("""
            UPDATE goal_stats
            SET pending_tasks = pending_tasks - 1
            WHERE goal_id = ?
            """, (goal_id,))

        # Agar task completed tha to completed count ghatao
        elif status == "completed":
            cur.execute("""
            UPDATE goal_stats
            SET completed_tasks = completed_tasks - 1
            WHERE goal_id = ?
            """, (goal_id,))

        conn.commit()

        return True

    except Exception as e:

        print(f"Delete Task Error: {e}")
        return False

    finally:

        conn.close()
def save_study_session(goal_id, minutes):

    conn = get_db()
    cur = conn.cursor()

    try:

        today = datetime.now().strftime("%Y-%m-%d")

        cur.execute("""
        INSERT INTO study_sessions(
            goal_id,
            study_date,
            minutes
        )
        VALUES(?,?,?)
        """, (
            goal_id,
            today,
            minutes
        ))

        # Goal Stats Update
        cur.execute("""
        UPDATE goal_stats
        SET study_hours = study_hours + ?
        WHERE goal_id = ?
        """, (
            minutes / 60,
            goal_id
        ))

        conn.commit()

        return True

    except Exception as e:

        print(f"Save Session Error: {e}")
        return False

    finally:

        conn.close()
from datetime import datetime

def get_today_study_time(goal_id):

    conn = get_db()
    cur = conn.cursor()

    try:

        today = datetime.now().strftime("%Y-%m-%d")

        cur.execute("""
        SELECT COALESCE(SUM(minutes), 0) AS total_minutes
        FROM study_sessions
        WHERE goal_id = ?
        AND study_date = ?
        """, (
            goal_id,
            today
        ))

        result = cur.fetchone()

        return result["total_minutes"]

    except Exception as e:

        print(f"Get Today Study Time Error: {e}")
        return 0

    finally:

        conn.close()
def get_study_history(goal_id):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
        SELECT *
        FROM study_sessions
        WHERE goal_id = ?
        ORDER BY study_date DESC, created_at DESC
        """, (goal_id,))

        sessions = cur.fetchall()

        return sessions

    except Exception as e:

        print(f"Study History Error: {e}")
        return []

    finally:

        conn.close()
from datetime import datetime, timedelta

def get_weekly_study_data(goal_id):

    conn = get_db()
    cur = conn.cursor()

    try:

        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=6)

        cur.execute("""
        SELECT
            study_date,
            SUM(minutes) as total_minutes
        FROM study_sessions
        WHERE goal_id = ?
        AND study_date BETWEEN ? AND ?
        GROUP BY study_date
        ORDER BY study_date ASC
        """, (
            goal_id,
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d")
        ))

        return cur.fetchall()

    except Exception as e:

        print(f"Weekly Study Data Error: {e}")
        return []

    finally:

        conn.close()
def get_dashboard_stats(goal_id):

    try:

        goal = get_goal(goal_id)

        tasks = get_tasks(goal_id)
        today_task = get_current_task(goal_id)

        today_minutes = get_today_study_time(goal_id)

        weekly_data = get_weekly_study_data(goal_id)

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
        SELECT *
        FROM goal_stats
        WHERE goal_id = ?
        """, (goal_id,))

        stats = cur.fetchone()

        conn.close()

        return {
            "goal": goal,
            "tasks": tasks,
            "today_task": today_task,
            "today_minutes": today_minutes,
            "weekly_data": weekly_data,
            "completed_tasks": stats["completed_tasks"] if stats else 0,
            "pending_tasks": stats["pending_tasks"] if stats else 0,
            "study_hours": stats["study_hours"] if stats else 0,
            "total_xp": stats["total_xp"] if stats else 0,
            "current_level": stats["current_level"] if stats else 1,
            "streak": stats["streak"] if stats else 0
        }

    except Exception as e:

        print(f"Dashboard Stats Error: {e}")

        return None
def update_progress(goal_id):

    conn = sqlite3.connect("eka_ai.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Completed Tasks
    cursor.execute("""
        SELECT COUNT(*) as total
        FROM tasks
    WHERE goal_id=? AND status='completed'
    """, (goal_id,))
    completed_tasks = cursor.fetchone()["total"]

    # Pending Tasks
    cursor.execute("""
        SELECT COUNT(*) as total
        FROM tasks
    WHERE goal_id=? AND status='pending'
    """, (goal_id,))
    pending_tasks = cursor.fetchone()["total"]

    # Study Time
    cursor.execute("""
        SELECT COALESCE(SUM(minutes),0) as total
        FROM study_sessions
        WHERE goal_id=?
    """, (goal_id,))
    study_minutes = cursor.fetchone()["total"]

    study_hours = round(study_minutes / 60, 1)

    # XP Formula
    total_xp = completed_tasks * 20 + int(study_hours * 10)

    # Level Formula
    level = (total_xp // 100) + 1

    cursor.execute("""
        UPDATE goals
        SET xp=?,
            level=?
        WHERE id=?
    """, (total_xp, level, goal_id))

    cursor.execute("""
        INSERT OR REPLACE INTO goal_stats(
            goal_id,
            completed_tasks,
            pending_tasks,
            study_hours,
            total_xp,
            current_level
        )
        VALUES (?,?,?,?,?,?)
    """, (
        goal_id,
        completed_tasks,
        pending_tasks,
        study_hours,
        total_xp,
        level
    ))

    conn.commit()
    conn.close()

    return True
def generate_ai_roadmap(
    goal_name,
    target_date,
    daily_hours,
    subjects,
    weak_subjects
):

    prompt = f"""
You are EKA AI.

Create a detailed study roadmap.

Goal:
{goal_name}

Target Date:
{target_date}

Daily Study Hours:
{daily_hours}

Subjects:
{subjects}

Weak Subjects:
{weak_subjects}

Return ONLY JSON.

Structure:

{{
  "months":[
      {{
          "month":1,
          "weeks":[
              {{
                  "week":1,
                  "tasks":[
                      {{
                          "title":"",
                          "description":"",
                          "minutes":60
                      }}
                  ]
              }}
          ]
      }}
  ]
}}
"""

    response = generate_ai_response(prompt)
    return response
import json

def parse_ai_roadmap(ai_response):
    """
    Convert Gemini JSON response into Python dictionary
    """

    try:
        # Agar AI ```json ... ``` me response de
        cleaned = ai_response.replace("```json", "").replace("```", "").strip()

        roadmap = json.loads(cleaned)

        return roadmap

    except json.JSONDecodeError as e:
        print("Roadmap Parse Error:", e)
        return None
def save_ai_roadmap(goal_id, roadmap):
    """Persist both the complete roadmap and its ordered daily tasks atomically."""
    if not isinstance(roadmap, dict) or not roadmap.get("months"):
        return False

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT target_date FROM goals WHERE id=?", (goal_id,))
        goal = cur.fetchone()
        if not goal:
            return False

        tasks = []
        for month in roadmap.get("months", []):
            for week in month.get("weeks", []):
                for task in week.get("tasks", []):
                    title = (task.get("title") or "").strip()
                    if title:
                        tasks.append((month.get("month", 1), week.get("week", 1), task))
        if not tasks:
            return False

        # A generated roadmap is immutable after it is saved; this prevents duplicates.
        cur.execute("SELECT COUNT(*) AS count FROM tasks WHERE goal_id=?", (goal_id,))
        if cur.fetchone()["count"]:
            return True

        today = datetime.now().date()
        try:
            target = datetime.strptime(goal["target_date"], "%Y-%m-%d").date()
            days_available = max((target - today).days + 1, 1)
        except (TypeError, ValueError):
            days_available = len(tasks)

        for index, (month_number, week_number, task) in enumerate(tasks, start=1):
            day_offset = min(index - 1, days_available - 1)
            due_date = (today + timedelta(days=day_offset)).strftime("%Y-%m-%d")
            description = (task.get("description") or "").strip()
            label = "Roadmap: Month %s, Week %s" % (month_number, week_number)
            description = label + ("\n" + description if description else "")
            cur.execute("""
            INSERT INTO tasks(goal_id, title, description, estimated_minutes, due_date, task_order)
            VALUES(?,?,?,?,?,?)
            """, (
                goal_id, task["title"].strip(), description,
                int(task.get("minutes", 60) or 60), due_date, index
            ))

        cur.execute("UPDATE goals SET roadmap=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (json.dumps(roadmap), goal_id))
        conn.commit()
        update_progress(goal_id)
        return True
    except Exception as e:
        conn.rollback()
        print("Save Roadmap Error:", e)
        return False
    finally:
        conn.close()
@app.route("/api/generate-roadmap", methods=["POST"])
def api_generate_roadmap():
    data = request.json

    goal_id = data["goal_id"]

    goal = get_goal(goal_id)

    if not goal:
        return jsonify({
            "success": False,
            "message": "Goal not found"
        }), 404

    # Return the saved roadmap on refresh/retry instead of asking the model again.
    if goal["roadmap"]:
        try:
            saved_roadmap = json.loads(goal["roadmap"])
        except (TypeError, json.JSONDecodeError):
            saved_roadmap = None
        if saved_roadmap:
            return jsonify({
                "success": True,
                "message": "Roadmap already generated",
                "roadmap": saved_roadmap,
                "today_task": get_current_task(goal_id)
            })

    ai_text = generate_ai_roadmap(
        goal["goal_name"],
        goal["target_date"],
        goal["daily_hours"],
        goal["subjects"],
        goal["weak_subjects"]
    )

    roadmap = parse_ai_roadmap(ai_text)

    if roadmap is None:
        return jsonify({
            "success": False,
            "message": "AI failed to generate roadmap"
        }), 500

    if not save_ai_roadmap(goal_id, roadmap):
        return jsonify({"success": False, "message": "Roadmap could not be saved"}), 500

    user_email = goal["user_email"]
    save_study_planner(
        user_email, goal["goal_name"], goal["target_date"], goal["daily_hours"],
        (goal["subjects"] or "").split(","),
        (goal["weak_subjects"] or "").split(","), roadmap
    )
    today_task = sync_planner_position(user_email, goal_id)

    return jsonify({
        "success": True,
        "message": "Roadmap generated successfully",
        "roadmap": roadmap,
        "today_task": today_task
    })

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

@app.route("/api/goals/<user_email>", methods=["GET"])
def api_get_goals(user_email):

    goals = get_all_goals(user_email)

    return jsonify({
        "success": True,
        "count": len(goals),
        "goals": goals
    })
@app.route("/api/goal/<int:goal_id>", methods=["GET"])
def api_get_goal(goal_id):

    goal = get_goal(goal_id)

    if not goal:
        return jsonify({
            "success": False,
            "message": "Goal not found"
        }), 404

    return jsonify({
        "success": True,
        "goal": goal
    })
@app.route("/api/goals", methods=["POST"])
def api_create_goal():

    data = request.json

    goal_id = create_goal(
        user_email=data["user_email"],
        goal_name=data["goal_name"],
        description=data.get("description", ""),
        category=data.get("category", "Study"),
        priority=data.get("priority", "Medium"),
        target_date=data.get("target_date"),
        daily_hours=data.get("daily_hours", 2),
        roadmap=data.get("roadmap", ""),
        subjects=data.get("subjects", ""),
        weak_subjects=data.get("weak_subjects", "")
    )

    if goal_id:
        return jsonify({
            "success": True,
            "goal_id": goal_id
        })

    return jsonify({
        "success": False,
        "message": "Goal creation failed"
    }), 400
@app.route("/api/goal/<int:goal_id>", methods=["PUT"])
def api_update_goal(goal_id):

    data = request.json

    success = update_goal(
        goal_id,
        data["goal_name"],
        data.get("description", ""),
        data.get("category", "Study"),
        data.get("priority", "Medium"),
        data.get("target_date"),
        data.get("daily_hours", 2),
        data.get("roadmap", ""),
        data.get("subjects", ""),
        data.get("weak_subjects", "")
    )

    return jsonify({
        "success": success
    })
@app.route("/api/goal/<int:goal_id>", methods=["DELETE"])
def api_delete_goal(goal_id):

    success = delete_goal(goal_id)

    return jsonify({
        "success": success
    })
@app.route("/api/tasks/<int:goal_id>", methods=["GET"])
def api_get_tasks(goal_id):

    tasks = get_tasks(goal_id)

    return jsonify({
        "success": True,
        "count": len(tasks),
        "tasks": tasks
    })
@app.route("/api/tasks", methods=["POST"])
def api_create_task():

    data = request.json

    task_id = create_task(
        goal_id=data["goal_id"],
        title=data["title"],
        description=data.get("description", ""),
        estimated_minutes=data.get("estimated_minutes", 30),
        due_date=data.get("due_date")
    )

    if task_id:
        return jsonify({
            "success": True,
            "task_id": task_id
        })

    return jsonify({
        "success": False,
        "message": "Task creation failed"
    }), 400
@app.route("/api/task/<int:task_id>", methods=["PUT"])
def api_update_task(task_id):

    data = request.json

    success = update_task(
        task_id,
        data["title"],
        data.get("description", ""),
        data.get("estimated_minutes", 30),
        data.get("due_date")
    )

    return jsonify({
        "success": success
    })
@app.route("/api/task/<int:task_id>/complete", methods=["POST"])
def api_complete_task(task_id):

    task = get_task(task_id)
    if not task:
        return jsonify({"success": False, "message": "Task not found"}), 404

    success = complete_task(task_id)
    if success:
        update_progress(task["goal_id"])
        goal = get_goal(task["goal_id"])
        if goal:
            next_task = sync_planner_position(goal["user_email"], task["goal_id"])
            sync_learning_memory(goal["user_email"], goal, next_task, task["title"])
    return jsonify({
        "success": success,
        "today_task": get_current_task(task["goal_id"]) if success else None
    })
@app.route("/api/study-session", methods=["POST"])
def api_save_study_session():

    data = request.json

    success = save_study_session(
        goal_id=data["goal_id"],
        minutes=data["minutes"]
    )

    if success:
        return jsonify({
            "success": True,
            "message": "Study session saved successfully"
        })

    return jsonify({
        "success": False,
        "message": "Failed to save study session"
    }), 400
@app.route("/api/study/today/<int:goal_id>", methods=["GET"])
def api_today_study(goal_id):

    minutes = get_today_study_time(goal_id)
    task = get_current_task(goal_id)

    return jsonify({
        "success": True,
        "today_minutes": minutes,
        "today_task": task
    })
@app.route("/api/study/history/<int:goal_id>", methods=["GET"])
def api_study_history(goal_id):

    history = get_study_history(goal_id)

    return jsonify({
        "success": True,
        "history": history
    })
@app.route("/api/study/weekly/<int:goal_id>", methods=["GET"])
def api_weekly_study(goal_id):

    weekly_data = get_weekly_study_data(goal_id)

    return jsonify({
        "success": True,
        "weekly_data": weekly_data
    })
@app.route("/api/dashboard/<int:goal_id>", methods=["GET"])
def api_dashboard(goal_id):

    dashboard = get_dashboard_stats(goal_id)

    if dashboard is None:
        return jsonify({
            "success": False,
            "message": "Dashboard data not found"
        }), 404

    return jsonify({
        "success": True,
        "dashboard": dashboard
    })

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
    if "user" in session:
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
        active_goal = get_active_goal(user_id)
        active_task = None
        if active_goal:
            command = (prompt or "").strip().lower()
            if command in ("next topic", "skip", "change topic"):
                active_task = skip_current_task(active_goal["id"])
            else:
                active_task = get_current_task(active_goal["id"])
            sync_planner_position(user_id, active_goal["id"])
            sync_learning_memory(user_id, active_goal, active_task, user_message=prompt)
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
        daily_task_context = ""
        if active_goal and active_task:
            daily_task_context = f"""

===== TODAY'S ASSIGNED ROADMAP TASK =====
Goal: {active_goal['goal_name']}
Task: {active_task['title']}
Task details: {active_task['description']}
Estimated minutes: {active_task['estimated_minutes']}
Task order: {active_task['task_order']}

Teach only this assigned task and continue it across chats until completion.
Never switch chapters or choose a random topic. Only a user request to next topic,
skip, or change topic may advance to the next roadmap task.
=========================================
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
        SYSTEM_PROMPT += "\n\n" + planner_context + daily_task_context
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

    # Roadmap state is authoritative over conversational extraction.
    active_goal = get_active_goal(user_id)
    if active_goal:
      sync_learning_memory(
          user_id,
          active_goal,
          get_current_task(active_goal["id"])
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

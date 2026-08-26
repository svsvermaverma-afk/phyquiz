import streamlit as st
import sqlite3
import pandas as pd
import time
from datetime import datetime
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Student Exam Portal",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed"
)

DB_FILE = "quiz_master.db"

# --- Database Initialization ---
def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    
    # Settings table (Stores Timing, Quiz Title, and Teacher's Student-Exam-Password)
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Questions table
    c.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_option TEXT NOT NULL
        )
    ''')
    
    # Overall Submissions table (Now includes Student Name)
    c.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            score INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            submitted_at TEXT NOT NULL
        )
    ''')
    
    # Detailed Question-wise Student Responses table
    c.execute('''
        CREATE TABLE IF NOT EXISTS student_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            email TEXT NOT NULL,
            question_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            selected_option TEXT,
            correct_option TEXT NOT NULL,
            is_correct INTEGER NOT NULL,
            recorded_at TEXT NOT NULL
        )
    ''')
    
    # Default Settings
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('duration_minutes', '15')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('quiz_title', 'Physics & Science Assessment')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('is_active', '1')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('student_exam_password', 'EXAM123')")
    
    # Sample Questions
    c.execute("SELECT COUNT(*) FROM questions")
    if c.fetchone()[0] == 0:
        sample_q = [
            ("What is the SI unit of Electric Current?", "Volt", "Ampere", "Ohm", "Watt", "Ampere"),
            ("Which sensor is used for gas/smoke detection?", "DHT11", "MQ2", "HC-SR04", "LDR", "MQ2"),
            ("What is the acceleration due to gravity on Earth?", "9.8 m/s²", "8.9 m/s²", "10.8 m/s²", "7.8 m/s²", "9.8 m/s²")
        ]
        c.executemany('''
            INSERT INTO questions (question, option_a, option_b, option_c, option_d, correct_option)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', sample_q)
        
    conn.commit()
    conn.close()

init_db()

# DB Helpers
def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def get_setting(key, default=""):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row['value'] if row else default

def get_questions():
    conn = get_db()
    df = pd.read_sql_query("SELECT * FROM questions", conn)
    conn.close()
    return df

# Anti-Cheating Scripts
def inject_security_scripts():
    js = """
    <script>
    window.addEventListener('blur', function() {
        alert('⚠️ Warning: Window/Tab switch detect hua hai! Yeh activity log ho rahi hai.');
    });
    document.addEventListener('contextmenu', function(e) { e.preventDefault(); });
    document.addEventListener('copy', function(e) { e.preventDefault(); });
    document.addEventListener('cut', function(e) { e.preventDefault(); });
    document.addEventListener('paste', function(e) { e.preventDefault(); });
    </script>
    """
    components.html(js, height=0, width=0)

# Session States
if "student_name" not in st.session_state:
    st.session_state.student_name = None
if "student_email" not in st.session_state:
    st.session_state.student_email = None
if "test_started" not in st.session_state:
    st.session_state.test_started = False
if "start_timestamp" not in st.session_state:
    st.session_state.start_timestamp = None

# ==========================================
# 1. STUDENT LOGIN PORTAL
# ==========================================
if not st.session_state.student_email:
    st.title("🎓 Student Examination Login Portal")
    st.markdown("Yeh platform strictly monitored hai. Apni details aur teacher dwara diya gaya **Exam Password** darj karein.")
    
    col1, _ = st.columns([1.2, 1])
    with col1:
        with st.form("student_login_form"):
            in_name = st.text_input("Student Full Name:", placeholder="Shashank Verma")
            in_email = st.text_input("Student Gmail ID (@gmail.com):", placeholder="student@gmail.com")
            in_pwd = st.text_input("Exam Password / Access PIN (Given by Teacher):", type="password")
            
            submit_login = st.form_submit_button("Enter Exam Portal", type="primary")
            
            if submit_login:
                clean_name = in_name.strip()
                clean_email = in_email.strip().lower()
                clean_pwd = in_pwd.strip()
                
                required_exam_pwd = get_setting("student_exam_password", "EXAM123")
                
                if not clean_name:
                    st.error("Kripya apna poora naam darj karein.")
                elif not (clean_email.endswith("@gmail.com") and len(clean_email) > 10):
                    st.error("Kripya ek valid Gmail ID darj karein (@gmail.com).")
                elif clean_pwd != required_exam_pwd:
                    st.error("Galat Exam Password! Sirf teacher ke diye huye password se hi login ho sakta hai.")
                else:
                    st.session_state.student_name = clean_name
                    st.session_state.student_email = clean_email
                    st.rerun()
    st.stop()

# ==========================================
# 2. STUDENT EXAM RUNTIME
# ==========================================
student_name = st.session_state.student_name
student_email = st.session_state.student_email

quiz_title = get_setting("quiz_title", "Online Examination")
quiz_duration = int(get_setting("duration_minutes", 15))
is_active = (get_setting("is_active", "1") == "1")

st.sidebar.markdown(f"**Student Name:** `{student_name}`")
st.sidebar.markdown(f"**Gmail:** `{student_email}`")

if st.sidebar.button("Log Out"):
    st.session_state.student_name = None
    st.session_state.student_email = None
    st.session_state.test_started = False
    st.session_state.start_timestamp = None
    st.rerun()

st.title(f"📝 {quiz_title}")

if not is_active:
    st.error("🛑 Yeh exam abhi active nahi hai. Kripya teacher/admin se sampark karein.")
    st.stop()

# Check if already submitted
conn = get_db()
c = conn.cursor()
c.execute("SELECT * FROM submissions WHERE email = ?", (student_email,))
submission = c.fetchone()
conn.close()

if submission:
    st.success(f"✅ {student_name}, aapka test pehle hi successfully submit ho chuka hai!")
    st.metric("Total Score", f"{submission['score']} / {submission['total_questions']}")
    st.info(f"Submitted Date & Time: {submission['submitted_at']}")
    st.stop()

questions_df = get_questions()
if questions_df.empty:
    st.info("Abhi exam me koi question upload nahi hua hai.")
    st.stop()

if not st.session_state.test_started:
    st.markdown("### 📌 Important Guidelines:")
    st.markdown(f"""
    - **Student Name:** `{student_name}`
    - **Total Duration:** `{quiz_duration} Minutes`
    - **Total Questions:** `{len(questions_df)}`
    - **Anti-Cheating Rules:**
        1. Dusri tab ya app switch karne par warning prompt aayegi aur report me log hoga.
        2. Copy-paste aur Right-click block rahenge.
        3. Timer start hone ke baad rukega nahi.
    """)
    if st.button("🚀 Start Examination Now", type="primary"):
        st.session_state.test_started = True
        st.session_state.start_timestamp = time.time()
        st.rerun()
    st.stop()

# Live Security Injection
inject_security_scripts()

# Timer Logic
elapsed = time.time() - st.session_state.start_timestamp
total_sec = quiz_duration * 60
remaining = total_sec - elapsed

if remaining <= 0:
    st.error("⏰ Time Up! Samay samapt ho gaya hai.")
    st.stop()

mins, secs = divmod(int(remaining), 60)
t1, t2 = st.columns([3, 1])
t1.markdown(f"Candidate: **{student_name}** (`{student_email}`)")
t2.metric("⏳ Time Remaining", f"{mins:02d}:{secs:02d}")
st.divider()

# Exam Form
with st.form("exam_form"):
    answers = {}
    for idx, row in questions_df.iterrows():
        st.markdown(f"**Q{idx+1}. {row['question']}**")
        opts = [row['option_a'], row['option_b'], row['option_c'], row['option_d']]
        answers[row['id']] = st.radio("Choose Option:", opts, key=f"q_{row['id']}", index=None)
        st.markdown("---")
        
    submitted = st.form_submit_button("Submit Final Answers", type="primary")
    
    if submitted:
        submission_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        score = 0
        
        conn = get_db()
        c = conn.cursor()
        
        for _, row in questions_df.iterrows():
            q_id = row['id']
            sel_opt = answers.get(q_id)
            correct_opt = row['correct_option']
            is_correct = 1 if (sel_opt == correct_opt) else 0
            if is_correct:
                score += 1
                
            c.execute('''
                INSERT INTO student_responses 
                (student_name, email, question_id, question_text, selected_option, correct_option, is_correct, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                student_name,
                student_email,
                q_id,
                row['question'],
                sel_opt if sel_opt else "Unattempted",
                correct_opt,
                is_correct,
                submission_time
            ))
            
        c.execute('''
            INSERT INTO submissions (student_name, email, score, total_questions, submitted_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (student_name, student_email, score, len(questions_df), submission_time))
        
        conn.commit()
        conn.close()
        
        st.balloons()
        st.success(f"🎉 Exam Successfully Submitted! Score: {score}/{len(questions_df)}")
        time.sleep(2)
        st.rerun()

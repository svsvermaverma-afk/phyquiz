import streamlit as st
import sqlite3
import pandas as pd
import time
from datetime import datetime
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Proctored Quiz & Exam Portal",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_FILE = "quiz_master.db"
ADMIN_EMAIL = "svsvermaverma@gmail.com"

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    
    # 1. Settings Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # 2. Questions Table
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
    
    # 3. Overall Submissions Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            score INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            submitted_at TEXT NOT NULL
        )
    ''')
    
    # 4. Detailed Student Answers Table (With Timestamp for each Q&A)
    c.execute('''
        CREATE TABLE IF NOT EXISTS student_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            question_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            selected_option TEXT,
            correct_option TEXT NOT NULL,
            is_correct INTEGER NOT NULL,
            recorded_at TEXT NOT NULL
        )
    ''')
    
    # Default initial data
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('duration_minutes', '15')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('quiz_title', 'Physics & Science Assessment')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('is_active', '1')")
    
    c.execute("SELECT COUNT(*) FROM questions")
    if c.fetchone()[0] == 0:
        sample_q = [
            ("What is the SI unit of Electric Current?", "Volt", "Ampere", "Ohm", "Watt", "Ampere"),
            ("Which sensor is used for gas detection?", "DHT11", "MQ2", "HC-SR04", "LDR", "MQ2"),
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

# Anti-Cheating JavaScript
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

# Session State
if "logged_email" not in st.session_state:
    st.session_state.logged_email = None
if "test_started" not in st.session_state:
    st.session_state.test_started = False
if "start_timestamp" not in st.session_state:
    st.session_state.start_timestamp = None

# ==========================================
# 1. LOGIN SCREEN (Gmail Only)
# ==========================================
if not st.session_state.logged_email:
    st.title("🔒 Online Assessment & Exam Portal")
    st.markdown("Yeh platform strictly monitored hai. Bina verified Gmail ID ke login nahi kiya ja sakta.")
    
    col1, _ = st.columns([1.2, 1])
    with col1:
        with st.form("login_form"):
            input_email = st.text_input("Apna Official Gmail ID Darj Karein:", placeholder="example@gmail.com")
            submit_btn = st.form_submit_button("Proceed / Sign In", type="primary")
            
            if submit_btn:
                email_clean = input_email.strip().lower()
                if email_clean.endswith("@gmail.com") and len(email_clean) > 10:
                    st.session_state.logged_email = email_clean
                    st.rerun()
                else:
                    st.error("Kripya ek valid Gmail ID darj karein jo '@gmail.com' par end hoti ho.")
    st.stop()

current_user = st.session_state.logged_email
is_admin = (current_user == ADMIN_EMAIL.lower())

# Sidebar Details
st.sidebar.markdown(f"**Logged In:** `{current_user}`")
if is_admin:
    st.sidebar.success("👑 Admin Mode Active")
    st.sidebar.info("Aap left sidebar ke '1_Admin_Panel' par jakar questions, timing aur printable reports manage kar sakte hain.")
else:
    st.sidebar.info("🎓 Student Examination Mode")

if st.sidebar.button("Log Out"):
    st.session_state.logged_email = None
    st.session_state.test_started = False
    st.session_state.start_timestamp = None
    st.rerun()

# ==========================================
# 2. STUDENT EXAM PORTAL
# ==========================================
quiz_title = get_setting("quiz_title", "Science Assessment")
quiz_duration = int(get_setting("duration_minutes", 15))
is_active = (get_setting("is_active", "1") == "1")

st.title(f"📝 {quiz_title}")

if not is_active:
    st.error("🛑 Yeh quiz abhi inactive hai. Kripya teacher/admin ke start karne ka wait karein.")
    st.stop()

# Check if already submitted
conn = get_db()
c = conn.cursor()
c.execute("SELECT * FROM submissions WHERE email = ?", (current_user,))
submission = c.fetchone()
conn.close()

if submission:
    st.success("✅ Aapka response successfully save ho chuka hai!")
    st.metric("Total Score", f"{submission['score']} / {submission['total_questions']}")
    st.info(f"Submitted Date & Time: {submission['submitted_at']}")
    st.stop()

questions_df = get_questions()
if questions_df.empty:
    st.info("Filhal koi question available nahi hai.")
    st.stop()

if not st.session_state.test_started:
    st.markdown("### 📌 Important Guidelines:")
    st.markdown(f"""
    - **Total Duration:** `{quiz_duration} Minutes`
    - **Total Questions:** `{len(questions_df)}`
    - **Rules:** Tab change na karein, Right-click block rahega. Har question ka answer time ke sath record hoga.
    """)
    if st.button("🚀 Start Exam Now", type="primary"):
        st.session_state.test_started = True
        st.session_state.start_timestamp = time.time()
        st.rerun()
    st.stop()

# Anti-Cheating Script Injection
inject_security_scripts()

# Timer Calculation
elapsed = time.time() - st.session_state.start_timestamp
total_sec = quiz_duration * 60
remaining = total_sec - elapsed

if remaining <= 0:
    st.error("⏰ Time Up! Test automatically close ho gaya hai.")
    st.stop()

mins, secs = divmod(int(remaining), 60)
t1, t2 = st.columns([3, 1])
t1.markdown(f"Candidate: **{current_user}**")
t2.metric("⏳ Time Left", f"{mins:02d}:{secs:02d}")
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
        
        # Save individual detailed answer logs
        for _, row in questions_df.iterrows():
            q_id = row['id']
            sel_opt = answers.get(q_id)
            correct_opt = row['correct_option']
            is_correct = 1 if (sel_opt == correct_opt) else 0
            if is_correct:
                score += 1
                
            c.execute('''
                INSERT INTO student_responses 
                (email, question_id, question_text, selected_option, correct_option, is_correct, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                current_user,
                q_id,
                row['question'],
                sel_opt if sel_opt else "Unattempted",
                correct_opt,
                is_correct,
                submission_time
            ))
            
        # Save overall submission
        c.execute('''
            INSERT INTO submissions (email, score, total_questions, submitted_at)
            VALUES (?, ?, ?, ?)
        ''', (current_user, score, len(questions_df), submission_time))
        
        conn.commit()
        conn.close()
        
        st.balloons()
        st.success(f"🎉 Exam Successfully Submitted! Score: {score}/{len(questions_df)}")
        time.sleep(2)
        st.rerun()

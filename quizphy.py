import streamlit as st
import sqlite3
import pandas as pd
import time
from datetime import datetime
import streamlit.components.v1 as components

# ==========================================
# 1. PAGE SETUP & CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="Proctored Quiz & Exam Portal",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_FILE = "quiz_master.db"

# Admin Login Credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@2026"

# ==========================================
# 2. DATABASE MANAGEMENT (SQLite)
# ==========================================
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
            student_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            score INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            submitted_at TEXT NOT NULL
        )
    ''')
    
    # 4. Detailed Question-wise Student Responses Table
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
    
    # Default sample questions
    c.execute("SELECT COUNT(*) FROM questions")
    if c.fetchone()[0] == 0:
        sample_q = [
            ("What is the SI unit of Electric Current?", "Volt", "Ampere", "Ohm", "Watt", "Ampere"),
            ("Which sensor is commonly used for gas/smoke detection?", "DHT11", "MQ2", "HC-SR04", "LDR", "MQ2"),
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

def update_setting(key, value):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

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
        alert('⚠️ Warning: Window/Tab switch detect hua hai! Yeh activity log ho chuki hai.');
    });
    document.addEventListener('contextmenu', function(e) { e.preventDefault(); });
    document.addEventListener('copy', function(e) { e.preventDefault(); });
    document.addEventListener('cut', function(e) { e.preventDefault(); });
    document.addEventListener('paste', function(e) { e.preventDefault(); });
    </script>
    """
    components.html(js, height=0, width=0)

# ==========================================
# 3. GLOBAL PORTAL NAVIGATION
# ==========================================
st.sidebar.title("🧭 Navigation")
selected_portal = st.sidebar.radio(
    "Select Access Portal:",
    ["🎓 Student Exam Portal", "⚙️ Admin Control Center"]
)
st.sidebar.divider()

# ==========================================
# ==========================================
# 4. ADMIN CONTROL CENTER
# ==========================================
# ==========================================
if selected_portal == "⚙️ Admin Control Center":
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False

    # Admin Login Gate
    if not st.session_state.admin_authenticated:
        st.title("🔐 Admin Control Login")
        st.markdown("Yeh section sirf teacher/incharge ke access ke liye hai.")
        
        col1, _ = st.columns([1.2, 1])
        with col1:
            with st.form("admin_login_form"):
                in_user = st.text_input("Admin Username:")
                in_pass = st.text_input("Admin Password:", type="password")
                btn_login = st.form_submit_button("Sign In as Admin", type="primary")
                
                if btn_login:
                    if in_user == ADMIN_USERNAME and in_pass == ADMIN_PASSWORD:
                        st.session_state.admin_authenticated = True
                        st.success("Admin Login Successful!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Galat Username ya Password! Access denied.")
        st.stop()

    # Admin Logged In Screen
    st.sidebar.success(f"👑 Admin Logged In: `{ADMIN_USERNAME}`")
    if st.sidebar.button("Log Out Admin"):
        st.session_state.admin_authenticated = False
        st.rerun()

    st.title("⚙️ Teacher / Admin Control Center")

    tab1, tab2, tab3 = st.tabs(["🖨️ Student Responses & Print", "⏱️ Exam Settings & Student Password", "📝 Question Bank"])

    # TAB 1: SUBMISSIONS & PRINTABLE A4
    with tab1:
        st.subheader("Student Results with Timestamp (Print Ready)")
        
        conn = get_db()
        subs_df = pd.read_sql_query(
            "SELECT student_name, email, score, total_questions, submitted_at FROM submissions ORDER BY id DESC", 
            conn
        )
        conn.close()
        
        if subs_df.empty:
            st.info("Abhi tak kisi bhi student ne test submit nahi kiya hai.")
        else:
            st.write("### 1. Overall Batch Results")
            st.dataframe(subs_df, use_container_width=True)
            
            csv_data = subs_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Batch CSV", data=csv_data, file_name="student_results.csv", mime="text/csv")
            
            st.divider()
            st.write("### 2. View & Print Individual Student Answer Sheet")
            
            student_display_list = [f"{r['student_name']} ({r['email']})" for _, r in subs_df.iterrows()]
            selected_option = st.selectbox("Select Student to Print Report:", student_display_list)
            
            if selected_option:
                selected_email = selected_option.split("(")[-1].replace(")", "").strip()
                
                conn = get_db()
                ans_df = pd.read_sql_query(
                    "SELECT student_name, question_text, selected_option, correct_option, is_correct, recorded_at FROM student_responses WHERE email = ?", 
                    conn, 
                    params=(selected_email,)
                )
                student_summary = conn.execute(
                    "SELECT student_name, score, total_questions, submitted_at FROM submissions WHERE email = ?", 
                    (selected_email,)
                ).fetchone()
                conn.close()
                
                html_content = f"""
                <div id="printableArea" style="font-family: Arial, sans-serif; border: 2px solid #333; padding: 25px; border-radius: 8px; background-color: #ffffff; color: #111;">
                    <div style="text-align: center; border-bottom: 2px solid #333; padding-bottom: 12px; margin-bottom: 20px;">
                        <h2 style="margin: 0; text-transform: uppercase; letter-spacing: 1px;">Official Student Examination Report</h2>
                        <p style="margin: 5px 0 0 0; color: #555;">Detailed Date-Time Performance Sheet</p>
                    </div>
                    
                    <table style="width: 100%; margin-bottom: 20px; font-size: 15px; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 6px 0;"><strong>Student Name:</strong> {student_summary['student_name']}</td>
                            <td style="padding: 6px 0; text-align: right;"><strong>Date & Time:</strong> {student_summary['submitted_at']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 6px 0;"><strong>Gmail ID:</strong> {selected_email}</td>
                            <td style="padding: 6px 0; text-align: right;"><strong>Final Score:</strong> <span style="font-size: 18px; color: #0b6623; font-weight: bold;">{student_summary['score']} / {student_summary['total_questions']}</span></td>
                        </tr>
                    </table>
                    
                    <table style="width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px;">
                        <thead>
                            <tr style="background-color: #f2f2f2; text-align: left;">
                                <th style="border: 1px solid #ccc; padding: 10px; width: 8%;">Q No.</th>
                                <th style="border: 1px solid #ccc; padding: 10px; width: 42%;">Question Statement</th>
                                <th style="border: 1px solid #ccc; padding: 10px; width: 20%;">Student Answer</th>
                                <th style="border: 1px solid #ccc; padding: 10px; width: 20%;">Correct Answer</th>
                                <th style="border: 1px solid #ccc; padding: 10px; width: 10%; text-align: center;">Result</th>
                            </tr>
                        </thead>
                        <tbody>
                """
                
                for idx, r in ans_df.iterrows():
                    badge = '<span style="color: green; font-weight: bold;">✔ Correct</span>' if r['is_correct'] == 1 else '<span style="color: red; font-weight: bold;">✖ Wrong</span>'
                    html_content += f"""
                        <tr>
                            <td style="border: 1px solid #ccc; padding: 8px; text-align: center;">{idx+1}</td>
                            <td style="border: 1px solid #ccc; padding: 8px;">{r['question_text']}</td>
                            <td style="border: 1px solid #ccc; padding: 8px;">{r['selected_option']}</td>
                            <td style="border: 1px solid #ccc; padding: 8px;">{r['correct_option']}</td>
                            <td style="border: 1px solid #ccc; padding: 8px; text-align: center;">{badge}</td>
                        </tr>
                    """
                    
                html_content += """
                        </tbody>
                    </table>
                    <div style="margin-top: 30px; text-align: right; font-size: 13px; color: #777;">
                        <p>Verified by Examination Incharge • Auto-generated Report</p>
                    </div>
                </div>
                """
                
                st.components.v1.html(f"""
                    {html_content}
                    <br>
                    <button onclick="window.print()" style="background-color: #007bff; color: white; border: none; padding: 10px 22px; font-size: 16px; border-radius: 6px; cursor: pointer; font-weight: bold;">🖨️ Print / Save as PDF This Answer Sheet</button>
                """, height=620, scrolling=True)

    # TAB 2: TIMING & EXAM PASSWORD
    with tab2:
        st.subheader("Quiz Timing & Student Exam Access Password")
        
        cur_title = get_setting("quiz_title", "Online Examination")
        cur_duration = int(get_setting("duration_minutes", 15))
        cur_active = (get_setting("is_active", "1") == "1")
        cur_student_pwd = get_setting("student_exam_password", "EXAM123")
        
        col1, col2 = st.columns(2)
        with col1:
            new_title = st.text_input("Quiz Title:", value=cur_title)
            new_duration = st.number_input("Duration (in Minutes):", min_value=1, max_value=300, value=cur_duration)
        with col2:
            new_student_pwd = st.text_input("Student Exam Password (Jo aap bachcho ko denge):", value=cur_student_pwd)
            new_active = st.toggle("Exam Active for Students", value=cur_active)
            
        if st.button("💾 Save Settings & Password", type="primary"):
            update_setting("quiz_title", new_title)
            update_setting("duration_minutes", new_duration)
            update_setting("student_exam_password", new_student_pwd)
            update_setting("is_active", "1" if new_active else "0")
            st.success("Settings aur Student Password successfully update ho gaye!")
            time.sleep(1)
            st.rerun()

    # TAB 3: QUESTION BANK
    with tab3:
        st.subheader("Manage Question Bank")
        
        with st.expander("➕ Add New Question", expanded=False):
            with st.form("add_q_form"):
                q_text = st.text_area("Question Statement:")
                c1, c2 = st.columns(2)
                op_a = c1.text_input("Option A:")
                op_b = c2.text_input("Option B:")
                op_c = c1.text_input("Option C:")
                op_d = c2.text_input("Option D:")
                
                correct_choice = st.selectbox("Select Correct Option:", ["Option A", "Option B", "Option C", "Option D"])
                
                if st.form_submit_button("Save Question"):
                    opts = {"Option A": op_a, "Option B": op_b, "Option C": op_c, "Option D": op_d}
                    if q_text and op_a and op_b and op_c and op_d:
                        conn = get_db()
                        c = conn.cursor()
                        c.execute('''
                            INSERT INTO questions (question, option_a, option_b, option_c, option_d, correct_option)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (q_text, op_a, op_b, op_c, op_d, opts[correct_choice]))
                        conn.commit()
                        conn.close()
                        st.success("Question add ho gaya!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Sabhi fields bharna zaroori hai.")

        st.markdown("---")
        conn = get_db()
        q_df = pd.read_sql_query("SELECT * FROM questions", conn)
        conn.close()
        
        for idx, row in q_df.iterrows():
            st.markdown(f"**Q{idx+1}. {row['question']}**")
            st.markdown(f"- A: `{row['option_a']}` | B: `{row['option_b']}` | C: `{row['option_c']}` | D: `{row['option_d']}`")
            st.markdown(f"🎯 **Answer:** `{row['correct_option']}`")
            
            if st.button(f"🗑️ Delete Q{idx+1}", key=f"del_q_{row['id']}"):
                conn = get_db()
                c = conn.cursor()
                c.execute("DELETE FROM questions WHERE id = ?", (row['id'],))
                conn.commit()
                conn.close()
                st.warning("Question delete ho gaya.")
                time.sleep(1)
                st.rerun()
            st.divider()

# ==========================================
# ==========================================
# 5. STUDENT EXAM PORTAL
# ==========================================
# ==========================================
else:
    if "student_name" not in st.session_state:
        st.session_state.student_name = None
    if "student_email" not in st.session_state:
        st.session_state.student_email = None
    if "test_started" not in st.session_state:
        st.session_state.test_started = False
    if "start_timestamp" not in st.session_state:
        st.session_state.start_timestamp = None

    # Student Login Gate
    if not st.session_state.student_email:
        st.title("🎓 Student Examination Login Portal")
        st.markdown("Yeh platform strictly monitored hai. Apni details aur teacher dwara diya gaya **Exam Password** darj karein.")
        
        col1, _ = st.columns([1.2, 1])
        with col1:
            with st.form("student_login_form"):
                in_name = st.text_input("Student Full Name:", placeholder="Shashank Verma")
                in_email = st.text_input("Student Gmail ID (@gmail.com):", placeholder="student@gmail.com")
                in_pwd = st.text_input("Exam Password (Given by Teacher):", type="password")
                
                submit_login = st.form_submit_button("Enter Exam Hall", type="primary")
                
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
                        st.error("Galat Exam Password! Sirf teacher ke diye huye password se login karein.")
                    else:
                        st.session_state.student_name = clean_name
                        st.session_state.student_email = clean_email
                        st.rerun()
        st.stop()

    # Student Dashboard / Exam Screen
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
        st.error("🛑 Yeh exam abhi active nahi hai. Kripya teacher se sampark karein.")
        st.stop()

    # Check already submitted
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
            1. Dusri tab ya app switch karne par warning prompt aayegi aur log save hoga.
            2. Copy-paste aur Right-click block rahenge.
            3. Ek baar start hone ke baad timer continuously chalega.
        """)
        if st.button("🚀 Start Examination Now", type="primary"):
            st.session_state.test_started = True
            st.session_state.start_timestamp = time.time()
            st.rerun()
        st.stop()

    # Proctoring JS injection
    inject_security_scripts()

    # Countdown Timer
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

    # Test Form
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

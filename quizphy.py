import streamlit as st
import sqlite3
import pandas as pd
import time
from datetime import datetime
import streamlit.components.v1 as components

# ==========================================
# 1. PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="Proctored Quiz Portal",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_FILE = "quiz_portal_v2.db"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@2026"

# ==========================================
# 2. BULLETPROOF DATABASE CONNECTION
# ==========================================
def get_db():
    conn = sqlite3.connect(DB_FILE, timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
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
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS authorized_students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT UNIQUE NOT NULL
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT UNIQUE NOT NULL,
            score INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            submitted_at TEXT NOT NULL
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS student_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
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
            ("Which sensor is commonly used for gas and smoke detection?", "DHT11", "MQ2", "HC-SR04", "LDR", "MQ2"),
            ("What is the acceleration due to gravity on Earth surface?", "9.8 m/s²", "8.9 m/s²", "10.8 m/s²", "7.8 m/s²", "9.8 m/s²")
        ]
        c.executemany('''
            INSERT INTO questions (question, option_a, option_b, option_c, option_d, correct_option)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', sample_q)
        
    conn.commit()
    conn.close()

init_db()

# DB Helpers
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

def get_authorized_students():
    conn = get_db()
    df = pd.read_sql_query("SELECT student_name FROM authorized_students", conn)
    conn.close()
    return [str(s).strip() for s in df['student_name'].tolist()]

# Anti-Cheating & Live Timer Component
def inject_live_timer_and_security(remaining_seconds):
    timer_js = f"""
    <div id="sticky-timer-box" style="
        position: fixed; 
        top: 60px; 
        right: 25px; 
        background: #ff4b4b; 
        color: #ffffff; 
        padding: 12px 24px; 
        border-radius: 10px; 
        font-family: monospace; 
        font-size: 22px; 
        font-weight: bold; 
        z-index: 999999;
        box-shadow: 0 4px 12px rgba(0,0,0,0.25);
        border: 2px solid white;
    ">
        ⏳ <span id="timer-display">Loading...</span>
    </div>

    <script>
    let timeLeft = {int(remaining_seconds)};
    let display = document.getElementById('timer-display');

    function updateTimer() {{
        if (timeLeft <= 0) {{
            display.innerHTML = "TIME UP!";
            display.style.color = "yellow";
            // Auto click submit button on time out
            let buttons = window.parent.document.querySelectorAll('button');
            buttons.forEach(btn => {{
                if (btn.innerText.includes("Submit Final Answers")) {{
                    btn.click();
                }}
            }});
            return;
        }}

        let mins = Math.floor(timeLeft / 60);
        let secs = timeLeft % 60;
        display.innerHTML = (mins < 10 ? "0" : "") + mins + ":" + (secs < 10 ? "0" : "") + secs;
        timeLeft--;
    }}

    updateTimer();
    setInterval(updateTimer, 1000);

    // Anti-Cheating Protection
    window.addEventListener('blur', function() {{
        alert('⚠️ Warning: Window switch detect hua hai! Yeh activity log ho chuki hai.');
    }});
    document.addEventListener('contextmenu', function(e) {{ e.preventDefault(); }});
    document.addEventListener('copy', function(e) {{ e.preventDefault(); }});
    document.addEventListener('cut', function(e) {{ e.preventDefault(); }});
    document.addEventListener('paste', function(e) {{ e.preventDefault(); }});
    </script>
    """
    components.html(timer_js, height=80)

# ==========================================
# 3. SIDEBAR NAVIGATION
# ==========================================
st.sidebar.title("🧭 Navigation")
selected_portal = st.sidebar.radio("Select Access Portal:", ["🎓 Student Exam Portal", "⚙️ Admin Control Center"])
st.sidebar.divider()

# ==========================================
# 4. ADMIN CONTROL PANEL
# ==========================================
if selected_portal == "⚙️ Admin Control Center":
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False

    # Admin Login
    if not st.session_state.admin_authenticated:
        st.title("🔐 Admin Login Portal")
        st.markdown("Yahan se sirf authorized teacher/admin access kar sakte hain.")
        
        col1, _ = st.columns([1.2, 1])
        with col1:
            with st.form("admin_login_form"):
                in_user = st.text_input("Admin Username:", placeholder="admin")
                in_pass = st.text_input("Admin Password:", type="password", placeholder="Admin@2026")
                btn_login = st.form_submit_button("Sign In as Admin", type="primary")
                
                if btn_login:
                    if in_user == ADMIN_USERNAME and in_pass == ADMIN_PASSWORD:
                        st.session_state.admin_authenticated = True
                        st.success("Admin Login Successful!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Galat Username ya Password!")
        st.stop()

    st.sidebar.success(f"👑 Admin Logged In: `{ADMIN_USERNAME}`")
    if st.sidebar.button("Log Out Admin"):
        st.session_state.admin_authenticated = False
        st.rerun()

    st.title("⚙️ Teacher / Admin Control Center")

    tab1, tab2, tab3, tab4 = st.tabs([
        "🖨️ Student Responses & Print", 
        "👥 Allowed Student Names (Excel/Manual)", 
        "📝 Question Bank (Excel/Manual)",
        "⏱️ Exam Settings & Password"
    ])

    # --- TAB 1: RESPONSES & PRINT ---
    with tab1:
        st.subheader("Student Results with Timestamp (Print Ready)")
        
        conn = get_db()
        try:
            subs_df = pd.read_sql_query(
                "SELECT student_name, score, total_questions, submitted_at FROM submissions ORDER BY id DESC", 
                conn
            )
        except Exception:
            subs_df = pd.DataFrame()
        conn.close()
        
        if subs_df.empty:
            st.info("Abhi tak kisi bhi student ne test submit nahi kiya hai.")
        else:
            st.write("### 1. Overall Batch Result")
            st.dataframe(subs_df, use_container_width=True)
            
            csv_data = subs_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Batch CSV", data=csv_data, file_name="student_results.csv", mime="text/csv")
            
            st.divider()
            st.write("### 2. View & Print Individual Student Answer Sheet")
            
            student_display_list = subs_df['student_name'].tolist()
            selected_student = st.selectbox("Select Student to Print Report:", student_display_list)
            
            if selected_student:
                conn = get_db()
                ans_df = pd.read_sql_query(
                    "SELECT student_name, question_text, selected_option, correct_option, is_correct, recorded_at FROM student_responses WHERE student_name = ?", 
                    conn, 
                    params=(selected_student,)
                )
                student_summary = conn.execute(
                    "SELECT student_name, score, total_questions, submitted_at FROM submissions WHERE student_name = ?", 
                    (selected_student,)
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
                            <td style="padding: 6px 0;"><strong>Final Score:</strong> <span style="font-size: 18px; color: #0b6623; font-weight: bold;">{student_summary['score']} / {student_summary['total_questions']}</span></td>
                            <td style="padding: 6px 0; text-align: right;"><strong>Status:</strong> Completed & Verified</td>
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

    # --- TAB 2: AUTHORIZED STUDENTS ---
    with tab2:
        st.subheader("👥 Manage Authorized Student Names")
        
        with st.expander("📂 Bulk Upload Students via Excel / CSV File", expanded=True):
            st.markdown("Excel file me pehla column **`student_name`** ya **`Name`** hona chahiye.")
            uploaded_students_file = st.file_uploader("Upload Excel (.xlsx) or CSV file of Students:", type=["xlsx", "csv"], key="stu_file")
            
            if uploaded_students_file is not None:
                try:
                    if uploaded_students_file.name.endswith(".csv"):
                        stu_df = pd.read_csv(uploaded_students_file)
                    else:
                        stu_df = pd.read_excel(uploaded_students_file)
                    
                    col_name = None
                    for c in stu_df.columns:
                        if c.strip().lower() in ["student_name", "name", "student name", "students"]:
                            col_name = c
                            break
                    
                    if col_name is None:
                        col_name = stu_df.columns[0]
                        
                    st.write("File Preview:")
                    st.dataframe(stu_df[[col_name]].head(5))
                    
                    if st.button("🚀 Import All Students from Excel"):
                        conn = get_db()
                        cur = conn.cursor()
                        added_count = 0
                        for name_val in stu_df[col_name].dropna().unique():
                            clean_n = str(name_val).strip()
                            if clean_n:
                                try:
                                    cur.execute("INSERT INTO authorized_students (student_name) VALUES (?)", (clean_n,))
                                    added_count += 1
                                except sqlite3.IntegrityError:
                                    pass
                        conn.commit()
                        conn.close()
                        st.success(f"Successfully {added_count} naye students add ho gaye!")
                        time.sleep(1)
                        st.rerun()
                except Exception as e:
                    st.error(f"File read karne me error: {e}")

        with st.expander("➕ Add Single Student Manually", expanded=False):
            with st.form("manual_add_stu"):
                new_student_name = st.text_input("Enter Student Full Name:")
                if st.form_submit_button("Add Student"):
                    clean_name = new_student_name.strip()
                    if clean_name:
                        try:
                            conn = get_db()
                            c = conn.cursor()
                            c.execute("INSERT INTO authorized_students (student_name) VALUES (?)", (clean_name,))
                            conn.commit()
                            conn.close()
                            st.success(f"'{clean_name}' successfully add ho gaya!")
                            time.sleep(1)
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.warning("Yeh student pehle se list me hai.")
                    else:
                        st.error("Kripya student ka naam enter karein.")
        
        st.markdown("---")
        st.write("### Current Allowed Students List")
        auth_list = get_authorized_students()
        st.write(f"Total Authorized Students: **{len(auth_list)}**")
        
        for name in auth_list:
            col_n1, col_n2 = st.columns([4, 1])
            col_n1.markdown(f"👤 **{name}**")
            if col_n2.button("Remove", key=f"rem_{name}"):
                conn = get_db()
                c = conn.cursor()
                c.execute("DELETE FROM authorized_students WHERE student_name = ?", (name,))
                conn.commit()
                conn.close()
                st.warning(f"'{name}' ko list se hata diya gaya.")
                time.sleep(1)
                st.rerun()

    # --- TAB 3: QUESTIONS BANK ---
    with tab3:
        st.subheader("📝 Manage Question Bank")
        
        with st.expander("📂 Bulk Upload Questions via Excel / CSV File", expanded=True):
            st.markdown("""
            **Excel format columns required:**
            `question`, `option_a`, `option_b`, `option_c`, `option_d`, `correct_option`
            """)
            uploaded_q_file = st.file_uploader("Upload Excel (.xlsx) or CSV file of Questions:", type=["xlsx", "csv"], key="q_file")
            
            if uploaded_q_file is not None:
                try:
                    if uploaded_q_file.name.endswith(".csv"):
                        q_file_df = pd.read_csv(uploaded_q_file)
                    else:
                        q_file_df = pd.read_excel(uploaded_q_file)
                        
                    q_file_df.columns = [str(c).strip().lower().replace(" ", "_") for c in q_file_df.columns]
                    
                    st.write("Preview of Uploaded Questions:")
                    st.dataframe(q_file_df.head(3))
                    
                    req_cols = ["question", "option_a", "option_b", "option_c", "option_d", "correct_option"]
                    if all(col in q_file_df.columns for col in req_cols):
                        if st.button("🚀 Import All Questions to Exam"):
                            conn = get_db()
                            cur = conn.cursor()
                            q_count = 0
                            for _, r in q_file_df.iterrows():
                                if pd.notna(r["question"]) and pd.notna(r["correct_option"]):
                                    cur.execute('''
                                        INSERT INTO questions (question, option_a, option_b, option_c, option_d, correct_option)
                                        VALUES (?, ?, ?, ?, ?, ?)
                                    ''', (
                                        str(r["question"]).strip(),
                                        str(r["option_a"]).strip(),
                                        str(r["option_b"]).strip(),
                                        str(r["option_c"]).strip(),
                                        str(r["option_d"]).strip(),
                                        str(r["correct_option"]).strip()
                                    ))
                                    q_count += 1
                            conn.commit()
                            conn.close()
                            st.success(f"Successfully {q_count} questions import ho gaye!")
                            time.sleep(1)
                            st.rerun()
                    else:
                        st.error("Excel file me sabhi columns hone zaroori hain: question, option_a, option_b, option_c, option_d, correct_option")
                except Exception as e:
                    st.error(f"Error reading file: {e}")

        with st.expander("➕ Add Single Question Manually", expanded=False):
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
                        st.error("Sabhi fields bharna compulsory hai.")

        st.markdown("---")
        conn = get_db()
        q_df = pd.read_sql_query("SELECT * FROM questions", conn)
        conn.close()
        
        st.write(f"Total Questions in Exam: **{len(q_df)}**")
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

    # --- TAB 4: TIMING & PASSWORD ---
    with tab4:
        st.subheader("⏱️ Exam Timing & Student Exam Access Password")
        
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
            st.success("Settings successfully save ho gayi hain!")
            time.sleep(1)
            st.rerun()

# ==========================================
# 5. STUDENT EXAM PORTAL (Live Real-Time Timer)
# ==========================================
else:
    if "student_name" not in st.session_state:
        st.session_state.student_name = None
    if "test_started" not in st.session_state:
        st.session_state.test_started = False
    if "start_timestamp" not in st.session_state:
        st.session_state.start_timestamp = None

    # Student Login Form
    if not st.session_state.student_name:
        st.title("🎓 Student Examination Login Portal")
        st.markdown("Kripya apna **Naam** aur teacher dwara diya gaya **Exam Password** darj karein.")
        
        col1, _ = st.columns([1.2, 1])
        with col1:
            with st.form("student_login_form"):
                in_name = st.text_input("Student Name (Jo list me registered hai):", placeholder="ABHISHEK GUPTA")
                in_pwd = st.text_input("Exam Password (Given by Teacher):", type="password")
                
                submit_login = st.form_submit_button("Enter Exam Portal", type="primary")
                
                if submit_login:
                    clean_name = in_name.strip()
                    clean_pwd = in_pwd.strip()
                    
                    required_exam_pwd = get_setting("student_exam_password", "EXAM123")
                    authorized_names = [name.lower() for name in get_authorized_students()]
                    
                    if not clean_name:
                        st.error("Kripya apna naam darj karein.")
                    elif clean_pwd != required_exam_pwd:
                        st.error("Galat Exam Password! Teacher dwara diya gaya password daalein.")
                    elif clean_name.lower() not in authorized_names:
                        st.error(f"❌ '{clean_name}' naam authorized list me nahi hai! Kripya teacher se sampark karein.")
                    else:
                        st.session_state.student_name = clean_name
                        st.rerun()
        st.stop()

    student_name = st.session_state.student_name

    quiz_title = get_setting("quiz_title", "Online Examination")
    quiz_duration = int(get_setting("duration_minutes", 15))
    is_active = (get_setting("is_active", "1") == "1")

    st.sidebar.markdown(f"**Student Candidate:** `{student_name}`")

    if st.sidebar.button("Log Out"):
        st.session_state.student_name = None
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
    try:
        c.execute("SELECT * FROM submissions WHERE LOWER(student_name) = ?", (student_name.lower(),))
        submission = c.fetchone()
    except Exception:
        submission = None
    conn.close()

    if submission:
        st.success(f"✅ {student_name}, aapka test pehle hi successfully submit ho chuka hai!")
        st.metric("Total Score", f"{submission['score']} / {submission['total_questions']}")
        st.info(f"Submitted Date & Time: {submission['submitted_at']}")
        st.stop()

    questions_df = get_questions()
    if questions_df.empty:
        st.info("Abhi exam me koi question available nahi hai.")
        st.stop()

    if not st.session_state.test_started:
        st.markdown("### 📌 Important Guidelines:")
        st.markdown(f"""
        - **Candidate Name:** `{student_name}`
        - **Total Duration:** `{quiz_duration} Minutes`
        - **Total Questions:** `{len(questions_df)}`
        - **Rules:**
            1. Screen ke top-right me live countdown timer chalega.
            2. Time khatam hone par test auto-submit ho jayega.
            3. Tab switch karne par system warning generate karega.
        """)
        if st.button("🚀 Start Examination Now", type="primary"):
            st.session_state.test_started = True
            st.session_state.start_timestamp = time.time()
            st.rerun()
        st.stop()

    # Remaining Seconds Calculation
    elapsed = time.time() - st.session_state.start_timestamp
    total_sec = quiz_duration * 60
    remaining = total_sec - elapsed

    if remaining <= 0:
        st.error("⏰ Time Up! Samay samapt ho gaya hai.")
        st.stop()

    # Live Floating Real-time Timer Inject
    inject_live_timer_and_security(remaining)

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
            
            # Save student responses
            for _, row in questions_df.iterrows():
                q_id = row['id']
                sel_opt = answers.get(q_id)
                correct_opt = row['correct_option']
                is_correct = 1 if (sel_opt == correct_opt) else 0
                if is_correct:
                    score += 1
                    
                c.execute('''
                    INSERT INTO student_responses 
                    (student_name, question_id, question_text, selected_option, correct_option, is_correct, recorded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    student_name,
                    q_id,
                    row['question'],
                    sel_opt if sel_opt else "Unattempted",
                    correct_opt,
                    is_correct,
                    submission_time
                ))
                
            # Save overall submission safely
            c.execute('''
                INSERT OR REPLACE INTO submissions (student_name, score, total_questions, submitted_at)
                VALUES (?, ?, ?, ?)
            ''', (student_name, score, len(questions_df), submission_time))
            
            conn.commit()
            conn.close()
            
            st.balloons()
            st.success(f"🎉 Exam Successfully Submitted! Score: {score}/{len(questions_df)}")
            time.sleep(2)
            st.rerun()

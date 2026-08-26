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
    page_title="Multi-Class Proctored Quiz Portal",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_FILE = "multi_quiz_portal_v3.db"
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
    
    # 1. Quizzes Table (Multiple Quizzes Support for Class 11, Class 12, etc.)
    c.execute('''
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_title TEXT UNIQUE NOT NULL,
            duration_minutes INTEGER DEFAULT 15,
            start_datetime TEXT NOT NULL,
            end_datetime TEXT NOT NULL,
            exam_password TEXT DEFAULT 'EXAM123',
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    # 2. Questions Bank Table (Linked with quiz_id)
    c.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_option TEXT NOT NULL,
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE
        )
    ''')
    
    # 3. Authorized Students Table (Linked with quiz_id)
    c.execute('''
        CREATE TABLE IF NOT EXISTS authorized_students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            student_name TEXT NOT NULL,
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE,
            UNIQUE(quiz_id, student_name)
        )
    ''')
    
    # 4. Overall Submissions Table (Tracks Tab Switches & Score)
    c.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            student_name TEXT NOT NULL,
            score INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            tab_switches INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Completed',
            submitted_at TEXT NOT NULL,
            UNIQUE(quiz_id, student_name)
        )
    ''')
    
    # 5. Question-Wise Responses Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS student_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            student_name TEXT NOT NULL,
            question_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            selected_option TEXT,
            correct_option TEXT NOT NULL,
            is_correct INTEGER NOT NULL,
            recorded_at TEXT NOT NULL
        )
    ''')
    
    # Insert Default Demo Quizzes if empty
    c.execute("SELECT COUNT(*) FROM quizzes")
    if c.fetchone()[0] == 0:
        default_start = datetime.now().strftime("%Y-%m-%d %H:%M")
        # Default 7 days future end time
        default_end = datetime.now().replace(day=datetime.now().day + 7).strftime("%Y-%m-%d %H:%M")
        
        c.execute('''
            INSERT INTO quizzes (quiz_title, duration_minutes, start_datetime, end_datetime, exam_password, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ("Class 11 - Physics Periodic Test", 15, default_start, default_end, "EXAM11", 1))
        
        q_id_1 = c.lastrowid
        c.executemany('''
            INSERT INTO questions (quiz_id, question, option_a, option_b, option_c, option_d, correct_option)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', [
            (q_id_1, "What is the SI unit of Force?", "Pascal", "Newton", "Joule", "Watt", "Newton"),
            (q_id_1, "Dimensional formula of Work is?", "[MLT-2]", "[ML2T-2]", "[MLT-1]", "[ML2T-1]", "[ML2T-2]")
        ])
        
        c.executemany('''
            INSERT INTO authorized_students (quiz_id, student_name)
            VALUES (?, ?)
        ''', [(q_id_1, "Aman Verma"), (q_id_1, "Rohan Sharma")])

        c.execute('''
            INSERT INTO quizzes (quiz_title, duration_minutes, start_datetime, end_datetime, exam_password, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ("Class 12 - Physics Board Mock", 20, default_start, default_end, "EXAM12", 1))
        
        q_id_2 = c.lastrowid
        c.executemany('''
            INSERT INTO questions (quiz_id, question, option_a, option_b, option_c, option_d, correct_option)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', [
            (q_id_2, "SI unit of Electric Charge is?", "Coulomb", "Ampere", "Volt", "Ohm", "Coulomb"),
            (q_id_2, "Permittivity of free space (epsilon_0) value is?", "8.85 x 10^-12", "9 x 10^9", "1.6 x 10^-19", "3 x 10^8", "8.85 x 10^-12")
        ])
        
        c.executemany('''
            INSERT INTO authorized_students (quiz_id, student_name)
            VALUES (?, ?)
        ''', [(q_id_2, "Abhishek Gupta"), (q_id_2, "Priya Singh")])

    conn.commit()
    conn.close()

init_db()

# DB Helper Functions
def get_db():
    conn = sqlite3.connect(DB_FILE, timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn

def get_all_quizzes():
    conn = get_db()
    df = pd.read_sql_query("SELECT * FROM quizzes", conn)
    conn.close()
    return df

def get_questions_by_quiz(quiz_id):
    conn = get_db()
    df = pd.read_sql_query("SELECT * FROM questions WHERE quiz_id = ?", conn, params=(quiz_id,))
    conn.close()
    return df

def get_authorized_students(quiz_id):
    conn = get_db()
    df = pd.read_sql_query("SELECT student_name FROM authorized_students WHERE quiz_id = ?", conn, params=(quiz_id,))
    conn.close()
    return [str(s).strip() for s in df['student_name'].tolist()]

# Live Timer & Advanced Anti-Cheating Script (Tab Switch Counter & Block)
def inject_live_timer_and_security(remaining_seconds, quiz_id, student_name):
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
        ⏳ <span id="timer-display">Loading...</span> | ⚠️ Switches: <span id="switch-count">0</span>
    </div>

    <script>
    let timeLeft = {int(remaining_seconds)};
    let display = document.getElementById('timer-display');
    let switchCountElem = document.getElementById('switch-count');
    let tabSwitches = sessionStorage.getItem('tab_switches_{quiz_id}_{student_name}') || 0;
    switchCountElem.innerHTML = tabSwitches;

    function updateTimer() {{
        if (timeLeft <= 0) {{
            display.innerHTML = "TIME UP!";
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

    // Strict Tab Switch Detection
    window.addEventListener('blur', function() {{
        tabSwitches++;
        sessionStorage.setItem('tab_switches_{quiz_id}_{student_name}', tabSwitches);
        switchCountElem.innerHTML = tabSwitches;
        
        // Send async log or alert
        alert('⚠️ WARNING (' + tabSwitches + '/3): Tab switch detect hua hai! Bar-bar tab badalne par test block ho jayega.');
        
        if (tabSwitches >= 3) {{
            alert('❌ Aapne limit se zyada baar tab switch kiya hai. Aapka test block kiya ja raha hai.');
            let buttons = window.parent.document.querySelectorAll('button');
            buttons.forEach(btn => {{
                if (btn.innerText.includes("Submit Final Answers")) {{
                    btn.click();
                }}
            }});
        }}
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

    st.title("⚙️ Multi-Class Quiz & Admin Management Center")

    quizzes_df = get_all_quizzes()
    
    admin_tab = st.selectbox("Select Management Section:", [
        "📊 Student Results & Tab Switch Logs", 
        "📚 Create & Manage Quizzes (Class 11, 12 etc.)", 
        "👥 Allowed Students (Excel/Manual)", 
        "📝 Question Bank (Excel/Manual)"
    ])

    st.divider()

    # --- SECTION 1: RESULTS & TAB SWITCH LOGS ---
    if admin_tab == "📊 Student Results & Tab Switch Logs":
        st.subheader("Student Submissions, Scores & Anti-Cheat Tab Switch Logs")
        
        if quizzes_df.empty:
            st.info("Pehle ek Quiz create karein.")
        else:
            quiz_options = {row['quiz_title']: row['id'] for _, row in quizzes_df.iterrows()}
            sel_q_title = st.selectbox("Select Quiz Class to View Results:", list(quiz_options.keys()))
            sel_q_id = quiz_options[sel_q_title]
            
            conn = get_db()
            try:
                subs_df = pd.read_sql_query(
                    "SELECT student_name, score, total_questions, tab_switches, status, submitted_at FROM submissions WHERE quiz_id = ? ORDER BY id DESC", 
                    conn, params=(sel_q_id,)
                )
            except Exception:
                subs_df = pd.DataFrame()
            conn.close()
            
            if subs_df.empty:
                st.info("Is quiz ke liye abhi tak koi submission nahi hai.")
            else:
                st.write("### Batch Performance & Security Audit Log")
                st.dataframe(subs_df, use_container_width=True)
                
                csv_data = subs_df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Results & Cheat Logs (CSV)", data=csv_data, file_name=f"{sel_q_title}_results.csv", mime="text/csv")
                
                st.divider()
                st.write("### 🖨️ Print Individual Answer Sheet")
                student_display_list = subs_df['student_name'].tolist()
                selected_student = st.selectbox("Select Student:", student_display_list)
                
                if selected_student:
                    conn = get_db()
                    ans_df = pd.read_sql_query(
                        "SELECT question_text, selected_option, correct_option, is_correct, recorded_at FROM student_responses WHERE quiz_id = ? AND student_name = ?", 
                        conn, params=(sel_q_id, selected_student)
                    )
                    student_summary = conn.execute(
                        "SELECT student_name, score, total_questions, tab_switches, submitted_at FROM submissions WHERE quiz_id = ? AND student_name = ?", 
                        (sel_q_id, selected_student)
                    ).fetchone()
                    conn.close()
                    
                    html_content = f"""
                    <div style="font-family: Arial, sans-serif; border: 2px solid #333; padding: 25px; border-radius: 8px; background-color: #fff; color: #111;">
                        <h2 style="text-align: center; text-transform: uppercase;">Official Assessment Report ({sel_q_title})</h2>
                        <table style="width: 100%; margin-bottom: 20px; font-size: 15px;">
                            <tr>
                                <td><strong>Student Name:</strong> {student_summary['student_name']}</td>
                                <td style="text-align: right;"><strong>Submitted At:</strong> {student_summary['submitted_at']}</td>
                            </tr>
                            <tr>
                                <td><strong>Score:</strong> <span style="color: green; font-weight: bold;">{student_summary['score']} / {student_summary['total_questions']}</span></td>
                                <td style="text-align: right;"><strong>Tab Switches Detected:</strong> <span style="color: red; font-weight: bold;">{student_summary['tab_switches']} times</span></td>
                            </tr>
                        </table>
                        <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                            <thead>
                                <tr style="background-color: #f2f2f2; text-align: left;">
                                    <th style="border: 1px solid #ccc; padding: 8px;">Q.No</th>
                                    <th style="border: 1px solid #ccc; padding: 8px;">Question</th>
                                    <th style="border: 1px solid #ccc; padding: 8px;">Student Answer</th>
                                    <th style="border: 1px solid #ccc; padding: 8px;">Correct Answer</th>
                                    <th style="border: 1px solid #ccc; padding: 8px; text-align: center;">Result</th>
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
                    html_content += "</tbody></table></div>"
                    
                    st.components.v1.html(f"""
                        {html_content}
                        <br>
                        <button onclick="window.print()" style="background-color: #007bff; color: white; border: none; padding: 10px 20px; font-size: 16px; border-radius: 5px; cursor: pointer; font-weight: bold;">🖨️ Print Report</button>
                    """, height=600, scrolling=True)

    # --- SECTION 2: CREATE & MANAGE QUIZZES ---
    elif admin_tab == "📚 Create & Manage Quizzes (Class 11, 12 etc.)":
        st.subheader("Manage Quizzes, Timings & Access Windows")
        
        with st.expander("➕ Create New Quiz (Class 11 / Class 12)", expanded=True):
            with st.form("new_quiz_form"):
                q_title = st.text_input("Quiz Title (e.g., Class 11 Physics Final):")
                q_dur = st.number_input("Duration (Minutes):", min_value=1, max_value=300, value=15)
                q_pwd = st.text_input("Student Exam Password:", value="EXAM123")
                
                c_d1, c_d2 = st.columns(2)
                start_date = c_d1.date_input("Start Date:")
                start_time = c_d1.time_input("Start Time:")
                end_date = c_d2.date_input("End Date:")
                end_time = c_d2.time_input("End Time:")
                
                submitted_quiz = st.form_submit_button("Create Quiz")
                if submitted_quiz:
                    start_str = f"{start_date} {start_time.strftime('%H:%M')}"
                    end_str = f"{end_date} {end_time.strftime('%H:%M')}"
                    if q_title:
                        try:
                            conn = get_db()
                            c = conn.cursor()
                            c.execute('''
                                INSERT INTO quizzes (quiz_title, duration_minutes, start_datetime, end_datetime, exam_password, is_active)
                                VALUES (?, ?, ?, ?, ?, 1)
                            ''', (q_title, q_dur, start_str, end_str, q_pwd))
                            conn.commit()
                            conn.close()
                            st.success(f"Quiz '{q_title}' successfully create ho gaya!")
                            time.sleep(1)
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Is naam se quiz pehle se maujood hai.")
                    else:
                        st.error("Quiz title bharna zaroori hai.")

        st.markdown("---")
        st.write("### Existing Quizzes")
        if not quizzes_df.empty:
            for _, r in quizzes_df.iterrows():
                with st.container():
                    st.markdown(f"**{r['quiz_title']}** | Duration: `{r['duration_minutes']} mins` | Password: `{r['exam_password']}`")
                    st.markdown(f"🕒 **Valid From:** `{r['start_datetime']}` **To:** `{r['end_datetime']}`")
                    
                    col_q1, col_q2 = st.columns(2)
                    if col_q1.button(f"Toggle Active Status ({r['quiz_title']})", key=f"tog_{r['id']}"):
                        new_status = 0 if r['is_active'] == 1 else 1
                        conn = get_db()
                        conn.execute("UPDATE quizzes SET is_active = ? WHERE id = ?", (new_status, r['id']))
                        conn.commit()
                        conn.close()
                        st.rerun()
                    st.divider()

    # --- SECTION 3: AUTHORIZED STUDENTS ---
    elif admin_tab == "👥 Allowed Students (Excel/Manual)":
        st.subheader("Manage Authorized Students for Specific Quiz")
        
        if quizzes_df.empty:
            st.info("Pehle ek Quiz create karein.")
        else:
            quiz_options = {row['quiz_title']: row['id'] for _, row in quizzes_df.iterrows()}
            sel_q_title = st.selectbox("Select Quiz / Class:", list(quiz_options.keys()), key="s_quiz")
            sel_q_id = quiz_options[sel_q_title]
            
            with st.expander("📂 Bulk Upload Students via Excel/CSV", expanded=True):
                uploaded_stu = st.file_uploader("Upload Excel/CSV:", type=["xlsx", "csv"], key="st_file")
                if uploaded_stu:
                    try:
                        df = pd.read_csv(uploaded_stu) if uploaded_stu.name.endswith(".csv") else pd.read_excel(uploaded_stu)
                        col_n = df.columns[0]
                        if st.button("Import Students"):
                            conn = get_db()
                            cur = conn.cursor()
                            cnt = 0
                            for name in df[col_n].dropna().unique():
                                clean_n = str(name).strip()
                                if clean_n:
                                    try:
                                        cur.execute("INSERT INTO authorized_students (quiz_id, student_name) VALUES (?, ?)", (sel_q_id, clean_n))
                                        cnt += 1
                                    except sqlite3.IntegrityError:
                                        pass
                            conn.commit()
                            conn.close()
                            st.success(f"{cnt} students added to {sel_q_title}!")
                            time.sleep(1)
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
            
            st.markdown("---")
            st.write(f"### Allowed Students in: {sel_q_title}")
            auth_list = get_authorized_students(sel_q_id)
            st.write(f"Total: {len(auth_list)}")
            for name in auth_list:
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"👤 {name}")
                if c2.button("Remove", key=f"rem_st_{sel_q_id}_{name}"):
                    conn = get_db()
                    conn.execute("DELETE FROM authorized_students WHERE quiz_id = ? AND student_name = ?", (sel_q_id, name))
                    conn.commit()
                    conn.close()
                    st.rerun()

    # --- SECTION 4: QUESTION BANK ---
    elif admin_tab == "📝 Question Bank (Excel/Manual)":
        st.subheader("Manage Question Bank for Specific Quiz")
        
        if quizzes_df.empty:
            st.info("Pehle ek Quiz create karein.")
        else:
            quiz_options = {row['quiz_title']: row['id'] for _, row in quizzes_df.iterrows()}
            sel_q_title = st.selectbox("Select Quiz / Class:", list(quiz_options.keys()), key="q_quiz")
            sel_q_id = quiz_options[sel_q_title]
            
            with st.expander("📂 Bulk Upload Questions via Excel/CSV", expanded=True):
                st.markdown("Columns required: `question`, `option_a`, `option_b`, `option_c`, `option_d`, `correct_option`")
                uploaded_q = st.file_uploader("Upload Questions File:", type=["xlsx", "csv"], key="q_file")
                if uploaded_q:
                    try:
                        df = pd.read_csv(uploaded_q) if uploaded_q.name.endswith(".csv") else pd.read_excel(uploaded_q)
                        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
                        if st.button("Import Questions"):
                            conn = get_db()
                            cur = conn.cursor()
                            cnt = 0
                            for _, r in df.iterrows():
                                cur.execute('''
                                    INSERT INTO questions (quiz_id, question, option_a, option_b, option_c, option_d, correct_option)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                ''', (sel_q_id, r["question"], r["option_a"], r["option_b"], r["option_c"], r["option_d"], r["correct_option"]))
                                cnt += 1
                            conn.commit()
                            conn.close()
                            st.success(f"{cnt} questions imported!")
                            time.sleep(1)
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

            st.markdown("---")
            q_df = get_questions_by_quiz(sel_q_id)
            st.write(f"Total Questions in {sel_q_title}: **{len(q_df)}**")
            for idx, row in q_df.iterrows():
                st.markdown(f"**Q{idx+1}. {row['question']}**")
                st.markdown(f"- A: `{row['option_a']}` | B: `{row['option_b']}` | C: `{row['option_c']}` | D: `{row['option_d']}`")
                st.markdown(f"🎯 **Answer:** `{row['correct_option']}`")
                if st.button(f"Delete Q{idx+1}", key=f"del_q_{row['id']}"):
                    conn = get_db()
                    conn.execute("DELETE FROM questions WHERE id = ?", (row['id'],))
                    conn.commit()
                    conn.close()
                    st.rerun()
                st.divider()

# ==========================================
# 5. STUDENT EXAM PORTAL (Class/Quiz Selector & Time Window)
# ==========================================
else:
    if "student_name" not in st.session_state:
        st.session_state.student_name = None
    if "selected_quiz_id" not in st.session_state:
        st.session_state.selected_quiz_id = None
    if "test_started" not in st.session_state:
        st.session_state.test_started = False
    if "start_timestamp" not in st.session_state:
        st.session_state.start_timestamp = None

    quizzes_df = get_all_quizzes()
    active_quizzes = quizzes_df[quizzes_df['is_active'] == 1] if not quizzes_df.empty else pd.DataFrame()

    if active_quizzes.empty:
        st.error("🛑 Filhal koi bhi exam active nahi hai. Kripya teacher se sampark karein.")
        st.stop()

    # Student Login Form
    if not st.session_state.student_name or not st.session_state.selected_quiz_id:
        st.title("🎓 Student Examination Login Portal")
        st.markdown("Apni class/quiz select karein, apna **Naam** aur **Exam Password** darj karein.")
        
        quiz_opts = {row['quiz_title']: row['id'] for _, row in active_quizzes.iterrows()}
        
        col1, _ = st.columns([1.2, 1])
        with col1:
            with st.form("student_login_form"):
                sel_quiz_title = st.selectbox("Select Quiz / Class:", list(quiz_opts.keys()))
                in_name = st.text_input("Student Name (As per authorized list):")
                in_pwd = st.text_input("Exam Password (Given by Teacher):", type="password")
                
                submit_login = st.form_submit_button("Enter Exam Portal", type="primary")
                
                if submit_login:
                    q_id = quiz_opts[sel_quiz_title]
                    clean_name = in_name.strip()
                    clean_pwd = in_pwd.strip()
                    
                    # Fetch Quiz Details & Timing
                    conn = get_db()
                    q_data = conn.execute("SELECT * FROM quizzes WHERE id = ?", (q_id,)).fetchone()
                    conn.close()
                    
                    auth_names = [n.lower() for n in get_authorized_students(q_id)]
                    
                    # Time Window Check
                    now = datetime.now()
                    start_dt = datetime.strptime(q_data['start_datetime'], "%Y-%m-%d %H:%M")
                    end_dt = datetime.strptime(q_data['end_datetime'], "%Y-%m-%d %H:%M")
                    
                    if not clean_name:
                        st.error("Kripya apna naam darj karein.")
                    elif clean_pwd != q_data['exam_password']:
                        st.error("Galat Exam Password!")
                    elif clean_name.lower() not in auth_names:
                        st.error(f"❌ '{clean_name}' is quiz ke liye authorized list me nahi hai.")
                    elif now < start_dt:
                        st.error(f"⏳ Exam abhi shuru nahi hua hai! Start Time: {q_data['start_datetime']}")
                    elif now > end_dt:
                        st.error(f"⏰ Exam ka samay samapt ho chuka hai! End Time: {q_data['end_datetime']}")
                    else:
                        st.session_state.student_name = clean_name
                        st.session_state.selected_quiz_id = q_id
                        st.rerun()
        st.stop()

    student_name = st.session_state.student_name
    quiz_id = st.session_state.selected_quiz_id

    conn = get_db()
    quiz_info = conn.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
    conn.close()

    st.sidebar.markdown(f"**Candidate:** `{student_name}`")
    st.sidebar.markdown(f"**Exam:** `{quiz_info['quiz_title']}`")

    if st.sidebar.button("Log Out"):
        st.session_state.student_name = None
        st.session_state.selected_quiz_id = None
        st.session_state.test_started = False
        st.session_state.start_timestamp = None
        st.rerun()

    st.title(f"📝 {quiz_info['quiz_title']}")

    # Check already submitted
    conn = get_db()
    sub_check = conn.execute("SELECT * FROM submissions WHERE quiz_id = ? AND LOWER(student_name) = ?", (quiz_id, student_name.lower())).fetchone()
    conn.close()

    if sub_check:
        st.success(f"✅ {student_name}, aapka test pehle hi successfully submit ho chuka hai!")
        st.metric("Score", f"{sub_check['score']} / {sub_check['total_questions']}")
        st.metric("Tab Switches Recorded", f"{sub_check['tab_switches']} times")
        st.stop()

    questions_df = get_questions_by_quiz(quiz_id)
    if questions_df.empty:
        st.info("Is quiz me abhi koi question add nahi kiya gaya hai.")
        st.stop()

    if not st.session_state.test_started:
        st.markdown("### 📌 Exam Guidelines & Anti-Cheat System:")
        st.markdown(f"""
        - **Duration:** `{quiz_info['duration_minutes']} Minutes`
        - **Total Questions:** `{len(questions_df)}`
        - **Strict Rules:**
            1. Tab switch / app minimize karne par warning aayegi aur count admin panel me log hoga.
            2. 3 ya usse zyada baar tab switch karne par test automatically block/submit ho jayega.
            3. Timer continuous chalega.
        """)
        if st.button("🚀 Start Exam Now", type="primary"):
            st.session_state.test_started = True
            st.session_state.start_timestamp = time.time()
            st.rerun()
        st.stop()

    # Timer calculation
    elapsed = time.time() - st.session_state.start_timestamp
    total_sec = quiz_info['duration_minutes'] * 60
    remaining = total_sec - elapsed

    if remaining <= 0:
        st.error("⏰ Time Up! Samay samapt ho gaya hai.")
        st.stop()

    inject_live_timer_and_security(remaining, quiz_id, student_name)

    # Quiz Form
    with st.form("exam_form"):
        answers = {}
        for idx, row in questions_df.iterrows():
            st.markdown(f"**Q{idx+1}. {row['question']}**")
            opts = [row['option_a'], row['option_b'], row['option_c'], row['option_d']]
            answers[row['id']] = st.radio("Choose Option:", opts, key=f"q_{row['id']}", index=None)
            st.markdown("---")
            
        submitted = st.form_submit_button("Submit Final Answers", type="primary")
        
        if submitted:
            sub_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            score = 0
            
            conn = get_db()
            cur = conn.cursor()
            
            for _, row in questions_df.iterrows():
                q_id_num = row['id']
                sel_opt = answers.get(q_id_num)
                correct_opt = row['correct_option']
                is_correct = 1 if (sel_opt == correct_opt) else 0
                if is_correct:
                    score += 1
                    
                cur.execute('''
                    INSERT INTO student_responses (quiz_id, student_name, question_id, question_text, selected_option, correct_option, is_correct, recorded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (quiz_id, student_name, q_id_num, row['question'], sel_opt if sel_opt else "Unattempted", correct_opt, is_correct, sub_time))
                
            cur.execute('''
                INSERT OR REPLACE INTO submissions (quiz_id, student_name, score, total_questions, tab_switches, status, submitted_at)
                VALUES (?, ?, ?, ?, 0, 'Completed', ?)
            ''', (quiz_id, student_name, score, len(questions_df), sub_time))
            
            conn.commit()
            conn.close()
            
            st.balloons()
            st.success(f"🎉 Exam Successfully Submitted! Score: {score}/{len(questions_df)}")
            time.sleep(2)
            st.rerun()

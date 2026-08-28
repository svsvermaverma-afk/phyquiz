import streamlit as st
import sqlite3
import pandas as pd
import time
import io
import os
import re
from datetime import datetime, timedelta, timezone
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

DB_FILE = "master_quiz_system_prod.db"
STUDENTS_FILE_DEFAULT = "students.xlsx"
QUESTIONS_FILE_DEFAULT = "questions.xlsx"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@2026"

IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_now():
    return datetime.now(timezone.utc).astimezone(IST)

def clean_text(text):
    if text is None or pd.isna(text):
        return ""
    text_str = str(text).strip()
    return re.sub(r'\s+', ' ', text_str)

def clean_sr_no(sr_val):
    if pd.isna(sr_val) or sr_val is None:
        return ""
    sr_str = str(sr_val).strip()
    if sr_str.endswith(".0"):
        sr_str = sr_str[:-2]
    return sr_str

# ==========================================
# 2. BULLETPROOF DATABASE MANAGEMENT
# ==========================================
def get_db():
    conn = sqlite3.connect(DB_FILE, timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # 1. Master Student Directory
    c.execute('''
        CREATE TABLE IF NOT EXISTS master_students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            sr_no TEXT NOT NULL,
            normalized_name TEXT UNIQUE NOT NULL
        )
    ''')
    
    # 2. Quizzes Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_title TEXT UNIQUE NOT NULL,
            duration_minutes INTEGER DEFAULT 15,
            start_datetime TEXT NOT NULL,
            end_datetime TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    # 3. Questions Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_option TEXT NOT NULL
        )
    ''')
    
    # 4. Overall Submissions Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            student_name TEXT NOT NULL,
            sr_no TEXT NOT NULL,
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
            sr_no TEXT NOT NULL,
            question_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            selected_option TEXT,
            correct_option TEXT NOT NULL,
            is_correct INTEGER NOT NULL,
            recorded_at TEXT NOT NULL
        )
    ''')
    
    # Default Quiz Setup
    now_time = get_ist_now() - timedelta(hours=1)
    default_start = now_time.strftime("%Y-%m-%d %H:%M")
    default_end = (now_time + timedelta(days=30)).strftime("%Y-%m-%d %H:%M")
    
    c.execute('''
        INSERT OR IGNORE INTO quizzes (quiz_title, duration_minutes, start_datetime, end_datetime, is_active)
        VALUES (?, ?, ?, ?, ?)
    ''', ("Class 11 - Physics Periodic Test", 15, default_start, default_end, 1))
    
    # -------------------------------------------------------------
    # Auto-load repository/domain Excel files on every server boot
    # -------------------------------------------------------------
    # 1. Check & Load students.xlsx or students.csv from repo
    for s_path in [STUDENTS_FILE_DEFAULT, "students.csv"]:
        if os.path.exists(s_path):
            try:
                s_df = pd.read_csv(s_path) if s_path.endswith(".csv") else pd.read_excel(s_path)
                s_df.columns = [str(col).strip().lower().replace(" ", "_") for col in s_df.columns]
                n_col = next((col for col in s_df.columns if col in ["name", "student_name", "student"]), s_df.columns[0])
                sr_col = next((col for col in s_df.columns if col in ["sr_no", "srno", "sr", "roll_no", "rollno", "id", "password"]), s_df.columns[1] if len(s_df.columns) > 1 else s_df.columns[0])
                
                for _, r in s_df.iterrows():
                    st_nm = clean_text(r[n_col])
                    st_sr = clean_sr_no(r[sr_col])
                    if st_nm and st_sr:
                        c.execute('''
                            INSERT INTO master_students (student_name, sr_no, normalized_name)
                            VALUES (?, ?, ?)
                            ON CONFLICT(normalized_name) DO UPDATE SET student_name=excluded.student_name, sr_no=excluded.sr_no
                        ''', (st_nm, st_sr, st_nm.lower()))
            except Exception:
                pass

    # 2. Check & Load questions.xlsx or questions.csv from repo
    for q_path in [QUESTIONS_FILE_DEFAULT, "questions.csv"]:
        if os.path.exists(q_path):
            try:
                q_df = pd.read_csv(q_path) if q_path.endswith(".csv") else pd.read_excel(q_path)
                q_df.columns = [str(col).strip().lower().replace(" ", "_") for col in q_df.columns]
                
                # Fetch first active quiz
                c.execute("SELECT id FROM quizzes ORDER BY id ASC LIMIT 1")
                first_q = c.fetchone()
                if first_q:
                    q_id_target = first_q[0]
                    c.execute("SELECT COUNT(*) FROM questions WHERE quiz_id = ?", (q_id_target,))
                    if c.fetchone()[0] == 0:
                        for _, qr in q_df.iterrows():
                            c.execute('''
                                INSERT INTO questions (quiz_id, question, option_a, option_b, option_c, option_d, correct_option)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                q_id_target,
                                str(qr["question"]).strip(),
                                str(qr["option_a"]).strip(),
                                str(qr["option_b"]).strip(),
                                str(qr["option_c"]).strip(),
                                str(qr["option_d"]).strip(),
                                str(qr["correct_option"]).strip()
                            ))
            except Exception:
                pass

    conn.commit()
    conn.close()

init_db()

# DB Helpers
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

# Anti-Cheating & Live Timer
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

    window.addEventListener('blur', function() {{
        tabSwitches++;
        sessionStorage.setItem('tab_switches_{quiz_id}_{student_name}', tabSwitches);
        switchCountElem.innerHTML = tabSwitches;
        
        alert('⚠️ WARNING (' + tabSwitches + '/3): Tab switch detect hua hai! Bar-bar tab badalne par test auto-submit ho jayega.');
        
        if (tabSwitches >= 3) {{
            alert('❌ Maximum limit reach ho gayi hai. Test auto-submit ho raha hai.');
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
        st.markdown("Authorized teacher/admin access.")
        
        col1, _ = st.columns([1.2, 1])
        with col1:
            with st.form("admin_login_form"):
                in_user = st.text_input("Admin Username:")
                in_pass = st.text_input("Admin Password:", type="password")
                btn_login = st.form_submit_button("Sign In as Admin", type="primary")
                
                if btn_login:
                    if in_user.strip() == ADMIN_USERNAME and in_pass.strip() == ADMIN_PASSWORD:
                        st.session_state.admin_authenticated = True
                        st.success("Admin Login Successful!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Galat Username ya Password! Access Denied.")
        st.stop()

    st.sidebar.success(f"👑 Admin Logged In: `{ADMIN_USERNAME}`")
    if st.sidebar.button("Log Out Admin"):
        st.session_state.admin_authenticated = False
        st.rerun()

    st.title("⚙️ Teacher & Exam Control Center")
    st.info(f"🕒 Current Indian Standard Time (IST): **{get_ist_now().strftime('%Y-%m-%d %I:%M %p')}**")

    quizzes_df = get_all_quizzes()
    
    admin_tab = st.selectbox("Select Management Section:", [
        "👥 Master Student Directory (Excel/Manual)", 
        "📚 Create & Manage Quizzes (Edit Date/Time & Controls)", 
        "📝 Question Bank (Excel/Manual)",
        "📊 Student Results & Delete Controls", 
        "💾 Full Database Backup & Restore (Excel)"
    ])

    st.divider()

    # --- SECTION 1: MASTER STUDENTS ---
    if admin_tab == "👥 Master Student Directory (Excel/Manual)":
        st.subheader("👥 Master Student Directory")
        st.markdown("""
        **Tip:** Agar aap GitHub repo me **`students.xlsx`** naam se file upload kar denge, to redeploy hone par bhi data kabhi delete nahi hoga.
        - Columns: **`name`** (Student Name) aur **`sr_no`** (SR Number as Password).
        """)
        
        with st.expander("📂 Bulk Upload via Web Interface", expanded=True):
            uploaded_master_stu = st.file_uploader("Upload Excel (.xlsx / .csv):", type=["xlsx", "csv"])
            if uploaded_master_stu:
                try:
                    df = pd.read_csv(uploaded_master_stu) if uploaded_master_stu.name.endswith(".csv") else pd.read_excel(uploaded_master_stu)
                    df.columns = [str(col).strip().lower().replace(" ", "_") for col in df.columns]
                    
                    name_col = next((col for col in df.columns if col in ["name", "student_name", "student", "studentname"]), df.columns[0])
                    sr_col = next((col for col in df.columns if col in ["sr_no", "srno", "sr", "roll_no", "rollno", "id", "password"]), df.columns[1] if len(df.columns) > 1 else df.columns[0])
                    
                    st.write("File Preview:")
                    st.dataframe(df[[name_col, sr_col]].head(5))
                    
                    if st.button("🚀 Import All Students"):
                        conn = get_db()
                        cur = conn.cursor()
                        added_cnt = 0
                        for _, r in df.iterrows():
                            s_name = clean_text(r[name_col])
                            s_sr = clean_sr_no(r[sr_col])
                            s_norm = s_name.lower()
                            
                            if s_name and s_sr:
                                try:
                                    cur.execute('''
                                        INSERT INTO master_students (student_name, sr_no, normalized_name)
                                        VALUES (?, ?, ?)
                                        ON CONFLICT(normalized_name) DO UPDATE SET student_name=excluded.student_name, sr_no=excluded.sr_no
                                    ''', (s_name, s_sr, s_norm))
                                    added_cnt += 1
                                except Exception:
                                    pass
                        conn.commit()
                        conn.close()
                        st.success(f"Successfully {added_cnt} students add ho gaye!")
                        time.sleep(1)
                        st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

        st.markdown("---")
        st.write("### Currently Registered Students")
        conn = get_db()
        master_df = pd.read_sql_query("SELECT student_name AS 'Student Name', sr_no AS 'SR No (Password)' FROM master_students ORDER BY student_name", conn)
        conn.close()
        
        if master_df.empty:
            st.info("Abhi koi student registered nahi hai.")
        else:
            st.write(f"Total Enrolled: **{len(master_df)} Students**")
            st.dataframe(master_df, use_container_width=True)

    # --- SECTION 2: CREATE & MANAGE QUIZZES ---
    elif admin_tab == "📚 Create & Manage Quizzes (Edit Date/Time & Controls)":
        st.subheader("Manage Quizzes, Timings & Deletions")
        
        with st.expander("➕ Create New Quiz", expanded=False):
            with st.form("new_quiz_form"):
                q_title = st.text_input("Quiz Title:")
                q_dur = st.number_input("Duration (Minutes):", min_value=1, max_value=300, value=15)
                
                c_d1, c_d2 = st.columns(2)
                cur_ist = get_ist_now()
                start_date = c_d1.date_input("Start Date (IST):", value=cur_ist.date())
                start_time = c_d1.time_input("Start Time (IST):", value=(cur_ist - timedelta(minutes=10)).time())
                end_date = c_d2.date_input("End Date (IST):", value=(cur_ist + timedelta(days=7)).date())
                end_time = c_d2.time_input("End Time (IST):", value=cur_ist.time())
                
                if st.form_submit_button("Create Quiz"):
                    start_str = f"{start_date} {start_time.strftime('%H:%M')}"
                    end_str = f"{end_date} {end_time.strftime('%H:%M')}"
                    c_title = clean_text(q_title)
                    if c_title:
                        try:
                            conn = get_db()
                            c = conn.cursor()
                            c.execute('''
                                INSERT INTO quizzes (quiz_title, duration_minutes, start_datetime, end_datetime, is_active)
                                VALUES (?, ?, ?, ?, 1)
                            ''', (c_title, q_dur, start_str, end_str))
                            conn.commit()
                            conn.close()
                            st.success(f"Quiz '{c_title}' ban gaya!")
                            time.sleep(1)
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Yeh quiz pehle se bana hua hai.")

        st.markdown("---")
        st.write("### Existing Quizzes List & Controls")
        if not quizzes_df.empty:
            for _, r in quizzes_df.iterrows():
                with st.container():
                    st.markdown(f"**{r['quiz_title']}** | Duration: `{r['duration_minutes']} mins` | Status: `{'Active' if r['is_active'] == 1 else 'Disabled'}`")
                    st.markdown(f"🕒 **Valid From:** `{r['start_datetime']}` **To:** `{r['end_datetime']}`")
                    
                    col_q1, col_q2, col_q3 = st.columns([1, 1.5, 1])
                    if col_q1.button(f"Toggle Active", key=f"tog_{r['id']}"):
                        new_status = 0 if r['is_active'] == 1 else 1
                        conn = get_db()
                        conn.execute("UPDATE quizzes SET is_active = ? WHERE id = ?", (new_status, r['id']))
                        conn.commit()
                        conn.close()
                        st.rerun()
                    
                    if col_q2.button(f"⚡ Start NOW (Instant Live)", key=f"now_{r['id']}"):
                        now_start = (get_ist_now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
                        now_end = (get_ist_now() + timedelta(days=10)).strftime("%Y-%m-%d %H:%M")
                        conn = get_db()
                        conn.execute("UPDATE quizzes SET start_datetime = ?, end_datetime = ?, is_active = 1 WHERE id = ?", (now_start, now_end, r['id']))
                        conn.commit()
                        conn.close()
                        st.success("Quiz abhi se LIVE kar diya gaya hai!")
                        time.sleep(1)
                        st.rerun()
                    
                    if col_q3.button(f"🗑️ Delete Quiz", key=f"del_quiz_{r['id']}", type="secondary"):
                        conn = get_db()
                        conn.execute("DELETE FROM quizzes WHERE id = ?", (r['id'],))
                        conn.commit()
                        conn.close()
                        st.warning(f"Quiz delete ho gaya.")
                        time.sleep(1)
                        st.rerun()
                    st.divider()

    # --- SECTION 3: QUESTION BANK ---
    elif admin_tab == "📝 Question Bank (Excel/Manual)":
        st.subheader("Manage Question Bank")
        st.markdown("**Tip:** Repo me **`questions.xlsx`** upload karne par questions permanent rahenge.")
        
        if quizzes_df.empty:
            st.info("Pehle ek Quiz create karein.")
        else:
            quiz_options = {row['quiz_title']: row['id'] for _, row in quizzes_df.iterrows()}
            sel_q_title = st.selectbox("Select Quiz:", list(quiz_options.keys()), key="q_quiz")
            sel_q_id = quiz_options[sel_q_title]
            
            with st.expander("📂 Bulk Upload Questions via Web", expanded=True):
                st.markdown("Columns: `question`, `option_a`, `option_b`, `option_c`, `option_d`, `correct_option`")
                uploaded_q = st.file_uploader("Upload Questions File:", type=["xlsx", "csv"], key="q_file")
                if uploaded_q:
                    try:
                        df = pd.read_csv(uploaded_q) if uploaded_q.name.endswith(".csv") else pd.read_excel(uploaded_q)
                        df.columns = [str(col).strip().lower().replace(" ", "_") for col in df.columns]
                        if st.button("Import Questions"):
                            conn = get_db()
                            cur = conn.cursor()
                            cnt = 0
                            for _, r in df.iterrows():
                                cur.execute('''
                                    INSERT INTO questions (quiz_id, question, option_a, option_b, option_c, option_d, correct_option)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                ''', (sel_q_id, str(r["question"]).strip(), str(r["option_a"]).strip(), str(r["option_b"]).strip(), str(r["option_c"]).strip(), str(r["option_d"]).strip(), str(r["correct_option"]).strip()))
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
            st.write(f"Total Questions: **{len(q_df)}**")
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

    # --- SECTION 4: STUDENT RESULTS ---
    elif admin_tab == "📊 Student Results & Delete Controls":
        st.subheader("Student Submissions & Performance Sheet")
        
        if quizzes_df.empty:
            st.info("Pehle ek Quiz create karein.")
        else:
            quiz_options = {row['quiz_title']: row['id'] for _, row in quizzes_df.iterrows()}
            sel_q_title = st.selectbox("Select Quiz to View Results:", list(quiz_options.keys()))
            sel_q_id = quiz_options[sel_q_title]
            
            conn = get_db()
            try:
                subs_df = pd.read_sql_query(
                    "SELECT student_name, sr_no, score, total_questions, tab_switches, status, submitted_at FROM submissions WHERE quiz_id = ? ORDER BY id DESC", 
                    conn, params=(sel_q_id,)
                )
            except Exception:
                subs_df = pd.DataFrame()
            conn.close()
            
            if subs_df.empty:
                st.info("Is quiz ke liye abhi koi submission nahi hai.")
            else:
                st.write("### Batch Result Log")
                st.dataframe(subs_df, use_container_width=True)
                
                csv_data = subs_df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Results (CSV)", data=csv_data, file_name=f"{sel_q_title}_results.csv", mime="text/csv")
                
                if st.button(f"🗑️ Clear ALL Submissions for {sel_q_title}", type="secondary"):
                    conn = get_db()
                    conn.execute("DELETE FROM submissions WHERE quiz_id = ?", (sel_q_id,))
                    conn.execute("DELETE FROM student_responses WHERE quiz_id = ?", (sel_q_id,))
                    conn.commit()
                    conn.close()
                    st.warning("Submissions delete ho gaye.")
                    time.sleep(1)
                    st.rerun()

    # --- SECTION 5: BACKUP & RESTORE ---
    elif admin_tab == "💾 Full Database Backup & Restore (Excel)":
        st.subheader("💾 Complete Data Backup & Restore")
        
        conn = get_db()
        stu_export = pd.read_sql_query("SELECT * FROM master_students", conn)
        q_export = pd.read_sql_query("SELECT * FROM quizzes", conn)
        ques_export = pd.read_sql_query("SELECT * FROM questions", conn)
        subs_export = pd.read_sql_query("SELECT * FROM submissions", conn)
        resp_export = pd.read_sql_query("SELECT * FROM student_responses", conn)
        conn.close()
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            stu_export.to_excel(writer, sheet_name='Master_Students', index=False)
            q_export.to_excel(writer, sheet_name='Quizzes', index=False)
            ques_export.to_excel(writer, sheet_name='Questions', index=False)
            subs_export.to_excel(writer, sheet_name='Submissions', index=False)
            resp_export.to_excel(writer, sheet_name='Responses', index=False)
        excel_data = output.getvalue()
        
        st.download_button(
            label="📥 Download Full Database Backup (.xlsx)",
            data=excel_data,
            file_name=f"Quiz_Portal_Complete_Backup_{get_ist_now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.divider()
        st.write("### 📤 Restore Data from Excel Backup")
        uploaded_backup = st.file_uploader("Upload previous Backup Excel file:", type=["xlsx"])
        
        if uploaded_backup:
            if st.button("🚀 Restore Complete Data Now"):
                try:
                    excel_file = pd.ExcelFile(uploaded_backup)
                    conn = get_db()
                    cur = conn.cursor()
                    
                    if 'Master_Students' in excel_file.sheet_names:
                        df_stu = pd.read_excel(excel_file, sheet_name='Master_Students')
                        for _, r in df_stu.iterrows():
                            nm = clean_text(r['student_name'])
                            sr = clean_sr_no(r['sr_no'])
                            cur.execute("INSERT OR REPLACE INTO master_students (id, student_name, sr_no, normalized_name) VALUES (?, ?, ?, ?)",
                                        (r['id'], nm, sr, nm.lower()))
                    
                    if 'Quizzes' in excel_file.sheet_names:
                        df_q = pd.read_excel(excel_file, sheet_name='Quizzes')
                        for _, r in df_q.iterrows():
                            cur.execute("INSERT OR REPLACE INTO quizzes (id, quiz_title, duration_minutes, start_datetime, end_datetime, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                                        (r['id'], clean_text(r['quiz_title']), r['duration_minutes'], r['start_datetime'], r['end_datetime'], r['is_active']))
                    
                    if 'Questions' in excel_file.sheet_names:
                        df_ques = pd.read_excel(excel_file, sheet_name='Questions')
                        for _, r in df_ques.iterrows():
                            cur.execute("INSERT OR REPLACE INTO questions (id, quiz_id, question, option_a, option_b, option_c, option_d, correct_option) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                        (r['id'], r['quiz_id'], r['question'], r['option_a'], r['option_b'], r['option_c'], r['option_d'], r['correct_option']))
                    
                    conn.commit()
                    conn.close()
                    st.success("✅ Sara data successfully restore ho gaya!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Restore failed: {e}")

# ==========================================
# 5. STUDENT EXAM PORTAL
# ==========================================
else:
    if "student_name" not in st.session_state:
        st.session_state.student_name = None
    if "student_sr" not in st.session_state:
        st.session_state.student_sr = None
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
        st.markdown("Apna Quiz select karein, apna **Registered Name** aur Password me apna **SR No** darj karein.")
        
        quiz_opts = {row['quiz_title']: row['id'] for _, row in active_quizzes.iterrows()}
        
        col1, _ = st.columns([1.2, 1])
        with col1:
            with st.form("student_login_form"):
                sel_quiz_title = st.selectbox("Select Quiz:", list(quiz_opts.keys()))
                in_name = st.text_input("Student Name (Registered):", placeholder="Shashank Verma")
                in_pwd = st.text_input("Password (Aapka SR No):", type="password")
                
                submit_login = st.form_submit_button("Enter Exam Portal", type="primary")
                
                if submit_login:
                    q_id = quiz_opts[sel_quiz_title]
                    clean_input_name = clean_text(in_name)
                    clean_input_pwd = clean_sr_no(in_pwd)
                    norm_input_name = clean_input_name.lower()
                    
                    conn = get_db()
                    q_data = conn.execute("SELECT * FROM quizzes WHERE id = ?", (q_id,)).fetchone()
                    student_data = conn.execute("SELECT * FROM master_students WHERE normalized_name = ?", (norm_input_name,)).fetchone()
                    conn.close()
                    
                    now_ist = get_ist_now().replace(tzinfo=None)
                    try:
                        start_dt = datetime.strptime(q_data['start_datetime'], "%Y-%m-%d %H:%M")
                        end_dt = datetime.strptime(q_data['end_datetime'], "%Y-%m-%d %H:%M")
                    except Exception:
                        start_dt = now_ist - timedelta(days=1)
                        end_dt = now_ist + timedelta(days=10)
                    
                    if not clean_input_name or not clean_input_pwd:
                        st.error("Kripya Naam aur Password (SR No) dono darj karein.")
                    elif not student_data:
                        st.error(f"❌ Student Name '{clean_input_name}' registered list me nahi mila!")
                    elif clean_sr_no(student_data['sr_no']) != clean_input_pwd:
                        st.error("Galat Password! (Password aapka SR Number hai).")
                    elif now_ist < start_dt:
                        st.error(f"⏳ Exam abhi shuru nahi hua hai! Start Time (IST): {q_data['start_datetime']}")
                    elif now_ist > end_dt:
                        st.error(f"⏰ Exam ka samay samapt ho chuka hai! End Time (IST): {q_data['end_datetime']}")
                    else:
                        st.session_state.student_name = student_data['student_name']
                        st.session_state.student_sr = clean_sr_no(student_data['sr_no'])
                        st.session_state.selected_quiz_id = q_id
                        st.rerun()
        st.stop()

    student_name = st.session_state.student_name
    student_sr = st.session_state.student_sr
    quiz_id = st.session_state.selected_quiz_id

    conn = get_db()
    quiz_info = conn.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
    conn.close()

    st.sidebar.markdown(f"**Candidate:** `{student_name}`")
    st.sidebar.markdown(f"**SR No:** `{student_sr}`")
    st.sidebar.markdown(f"**Exam:** `{quiz_info['quiz_title']}`")

    if st.sidebar.button("Log Out"):
        st.session_state.student_name = None
        st.session_state.student_sr = None
        st.session_state.selected_quiz_id = None
        st.session_state.test_started = False
        st.session_state.start_timestamp = None
        st.rerun()

    st.title(f"📝 {quiz_info['quiz_title']}")

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
        - **Student Name:** `{student_name}` (SR: `{student_sr}`)
        - **Duration:** `{quiz_info['duration_minutes']} Minutes`
        - **Total Questions:** `{len(questions_df)}`
        - **Rules:**
            1. Tab switch karne par warning aayegi aur count record hoga.
            2. 3 baar tab switch karne par test auto-submit ho jayega.
            3. Timer continuous chalega.
        """)
        if st.button("🚀 Start Exam Now", type="primary"):
            st.session_state.test_started = True
            st.session_state.start_timestamp = time.time()
            st.rerun()
        st.stop()

    elapsed = time.time() - st.session_state.start_timestamp
    total_sec = quiz_info['duration_minutes'] * 60
    remaining = total_sec - elapsed

    if remaining <= 0:
        st.error("⏰ Time Up! Samay samapt ho gaya hai.")
        st.stop()

    inject_live_timer_and_security(remaining, quiz_id, student_name)

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
            sub_time = get_ist_now().strftime("%Y-%m-%d %H:%M:%S")
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
                    INSERT INTO student_responses (quiz_id, student_name, sr_no, question_id, question_text, selected_option, correct_option, is_correct, recorded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (quiz_id, student_name, student_sr, q_id_num, row['question'], sel_opt if sel_opt else "Unattempted", correct_opt, is_correct, sub_time))
                
            cur.execute('''
                INSERT OR REPLACE INTO submissions (quiz_id, student_name, sr_no, score, total_questions, tab_switches, status, submitted_at)
                VALUES (?, ?, ?, ?, ?, 0, 'Completed', ?)
            ''', (quiz_id, student_name, student_sr, score, len(questions_df), sub_time))
            
            conn.commit()
            conn.close()
            
            st.balloons()
            st.success(f"🎉 Exam Successfully Submitted! Score: {score}/{len(questions_df)}")
            time.sleep(2)
            st.rerun()

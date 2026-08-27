import streamlit as st
import sqlite3
import pandas as pd
import time
import io
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

DB_FILE = "master_quiz_system_v11.db"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@2026"

# Indian Standard Time (IST)
IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_now():
    return datetime.now(timezone.utc).astimezone(IST)

# Clean String Helper (Spaces aur Float issues theek karne ke liye)
def clean_str(val):
    if val is None or pd.isna(val):
        return ""
    s = str(val).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s

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
    
    # 1. Master Student Directory Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS master_students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT UNIQUE NOT NULL,
            sr_no TEXT NOT NULL
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
    
    # Demo Data Initialization
    now_time = get_ist_now() - timedelta(hours=1)
    default_start = now_time.strftime("%Y-%m-%d %H:%M")
    default_end = (now_time + timedelta(days=30)).strftime("%Y-%m-%d %H:%M")
    
    # Demo Students (Name, SR No)
    c.execute('''
        INSERT OR IGNORE INTO master_students (student_name, sr_no)
        VALUES 
        ('Aman Verma', '101'),
        ('Rohan Sharma', '102'),
        ('Shashank Verma', '103'),
        ('Abhishek Gupta', '201'),
        ('Priya Singh', '202')
    ''')
    
    # Demo Quizzes
    c.execute('''
        INSERT OR IGNORE INTO quizzes (quiz_title, duration_minutes, start_datetime, end_datetime, is_active)
        VALUES (?, ?, ?, ?, ?)
    ''', ("Class 11 - Physics Periodic Test", 15, default_start, default_end, 1))
    
    c.execute("SELECT id FROM quizzes WHERE quiz_title = ?", ("Class 11 - Physics Periodic Test",))
    row1 = c.fetchone()
    if row1:
        q_id_1 = row1[0]
        c.execute("SELECT COUNT(*) FROM questions WHERE quiz_id = ?", (q_id_1,))
        if c.fetchone()[0] == 0:
            c.executemany('''
                INSERT INTO questions (quiz_id, question, option_a, option_b, option_c, option_d, correct_option)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', [
                (q_id_1, "What is the SI unit of Force?", "Pascal", "Newton", "Joule", "Watt", "Newton"),
                (q_id_1, "Dimensional formula of Work is?", "[MLT-2]", "[ML2T-2]", "[MLT-1]", "[ML2T-1]", "[ML2T-2]")
            ])

    c.execute('''
        INSERT OR IGNORE INTO quizzes (quiz_title, duration_minutes, start_datetime, end_datetime, is_active)
        VALUES (?, ?, ?, ?, ?)
    ''', ("Class 12 - Physics Board Mock", 20, default_start, default_end, 1))
    
    c.execute("SELECT id FROM quizzes WHERE quiz_title = ?", ("Class 12 - Physics Board Mock",))
    row2 = c.fetchone()
    if row2:
        q_id_2 = row2[0]
        c.execute("SELECT COUNT(*) FROM questions WHERE quiz_id = ?", (q_id_2,))
        if c.fetchone()[0] == 0:
            c.executemany('''
                INSERT INTO questions (quiz_id, question, option_a, option_b, option_c, option_d, correct_option)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', [
                (q_id_2, "SI unit of Electric Charge is?", "Coulomb", "Ampere", "Volt", "Ohm", "Coulomb"),
                (q_id_2, "Permittivity of free space (epsilon_0) value is?", "8.85 x 10^-12", "9 x 10^9", "1.6 x 10^-19", "3 x 10^8", "8.85 x 10^-12")
            ])

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

def get_master_students_list():
    conn = get_db()
    df = pd.read_sql_query("SELECT student_name, sr_no FROM master_students ORDER BY student_name", conn)
    conn.close()
    return df

# Live Real-time Timer & Anti-Cheating Script
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

    // Tab Switch Detection & Warning
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

    # Secure Admin Login Screen
    if not st.session_state.admin_authenticated:
        st.title("🔐 Admin Login Portal")
        st.markdown("Yahan se sirf authorized teacher/admin access kar sakte hain.")
        
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
        "👥 Master Student Directory (Upload Excel: Name + SR No)", 
        "📚 Create & Manage Quizzes (Edit Date/Time & Controls)", 
        "📝 Question Bank (Excel/Manual)",
        "📊 Student Results & Delete Controls", 
        "💾 Full Database Backup & Restore (Excel)"
    ])

    st.divider()

    # --- SECTION 1: MASTER STUDENT DIRECTORY (2 COLUMNS EXCEL) ---
    if admin_tab == "👥 Master Student Directory (Upload Excel: Name + SR No)":
        st.subheader("👥 Master Student Directory (Upload Once)")
        st.markdown("""
        Excel file me **sirf 2 Columns** hone chahiye:
        - Column 1: **`name`** (Student ka poora naam)
        - Column 2: **`sr_no`** (Student ka SR No / Roll No - **Yahi uska Login Password hoga**)
        """)
        
        with st.expander("📂 Bulk Upload Master Students Excel / CSV (2 Columns)", expanded=True):
            uploaded_master_stu = st.file_uploader("Upload Excel (.xlsx / .csv):", type=["xlsx", "csv"])
            if uploaded_master_stu:
                try:
                    df = pd.read_csv(uploaded_master_stu) if uploaded_master_stu.name.endswith(".csv") else pd.read_excel(uploaded_master_stu)
                    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
                    
                    # Clean detection
                    name_col = next((c for c in df.columns if c in ["name", "student_name", "student"]), df.columns[0])
                    sr_col = next((c for c in df.columns if c in ["sr_no", "srno", "roll_no", "rollno", "id", "password"]), df.columns[1] if len(df.columns) > 1 else df.columns[0])
                    
                    # Data clean preview
                    clean_df = pd.DataFrame()
                    clean_df["Student Name"] = df[name_col].apply(clean_str)
                    clean_df["SR No (Password)"] = df[sr_col].apply(clean_str)
                    clean_df = clean_df[(clean_df["Student Name"] != "") & (clean_df["SR No (Password)"] != "")]
                    
                    st.write("Clean Data Preview (First 5 Rows):")
                    st.dataframe(clean_df.head(5))
                    
                    if st.button("🚀 Import All Students to Master Directory"):
                        conn = get_db()
                        cur = conn.cursor()
                        added_cnt = 0
                        for _, r in clean_df.iterrows():
                            s_name = r["Student Name"]
                            s_sr = r["SR No (Password)"]
                            
                            try:
                                cur.execute('''
                                    INSERT INTO master_students (student_name, sr_no)
                                    VALUES (?, ?)
                                    ON CONFLICT(student_name) DO UPDATE SET sr_no=excluded.sr_no
                                ''', (s_name, s_sr))
                                added_cnt += 1
                            except Exception:
                                pass
                        conn.commit()
                        conn.close()
                        st.success(f"Successfully {added_cnt} students add/update ho gaye!")
                        time.sleep(1)
                        st.rerun()
                except Exception as e:
                    st.error(f"Error reading file: {e}")

        with st.expander("➕ Add Single Student Manually"):
            with st.form("manual_student_form"):
                m_name = st.text_input("Student Name:")
                m_sr = st.text_input("SR No (Student Login Password):")
                
                if st.form_submit_button("Save Student"):
                    c_name = clean_str(m_name)
                    c_sr = clean_str(m_sr)
                    if c_name and c_sr:
                        conn = get_db()
                        conn.execute('''
                            INSERT INTO master_students (student_name, sr_no)
                            VALUES (?, ?)
                            ON CONFLICT(student_name) DO UPDATE SET sr_no=?
                        ''', (c_name, c_sr, c_sr))
                        conn.commit()
                        conn.close()
                        st.success(f"Student '{c_name}' (SR: {c_sr}) add ho gaya!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Dono fields bharna zaroori hai.")

        st.markdown("---")
        st.write("### Current Registered Students List")
        master_df = get_master_students_list()
        
        if master_df.empty:
            st.info("Abhi master list me koi student nahi hai.")
        else:
            st.write(f"Total Enrolled Students: **{len(master_df)}**")
            st.dataframe(master_df, use_container_width=True)
            
            c_del1, c_del2 = st.columns([3, 1])
            del_student_selected = c_del1.selectbox("Select Student to Delete:", master_df['student_name'].tolist())
            if c_del2.button(f"🗑️ Delete Student"):
                conn = get_db()
                conn.execute("DELETE FROM master_students WHERE student_name = ?", (del_student_selected,))
                conn.commit()
                conn.close()
                st.warning(f"Student '{del_student_selected}' delete ho gaya.")
                time.sleep(1)
                st.rerun()

    # --- SECTION 2: CREATE & MANAGE QUIZZES ---
    elif admin_tab == "📚 Create & Manage Quizzes (Edit Date/Time & Controls)":
        st.subheader("Manage Quizzes, Timings & Deletions")
        
        # 1. Create New Quiz
        with st.expander("➕ Create New Quiz", expanded=False):
            with st.form("new_quiz_form"):
                q_title = st.text_input("Quiz Title (e.g., Class 11 Physics Periodic Test):")
                q_dur = st.number_input("Duration (Minutes):", min_value=1, max_value=300, value=15)
                
                c_d1, c_d2 = st.columns(2)
                cur_ist = get_ist_now()
                start_date = c_d1.date_input("Start Date (IST):", value=cur_ist.date())
                start_time = c_d1.time_input("Start Time (IST):", value=(cur_ist - timedelta(minutes=10)).time())
                end_date = c_d2.date_input("End Date (IST):", value=(cur_ist + timedelta(days=7)).date())
                end_time = c_d2.time_input("End Time (IST):", value=cur_ist.time())
                
                submitted_quiz = st.form_submit_button("Create Quiz")
                if submitted_quiz:
                    start_str = f"{start_date} {start_time.strftime('%H:%M')}"
                    end_str = f"{end_date} {end_time.strftime('%H:%M')}"
                    if q_title:
                        try:
                            conn = get_db()
                            c = conn.cursor()
                            c.execute('''
                                INSERT INTO quizzes (quiz_title, duration_minutes, start_datetime, end_datetime, is_active)
                                VALUES (?, ?, ?, ?, 1)
                            ''', (q_title.strip(), q_dur, start_str, end_str))
                            conn.commit()
                            conn.close()
                            st.success(f"Quiz '{q_title}' successfully ban gaya!")
                            time.sleep(1)
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Is naam se quiz pehle se bana hua hai.")
                    else:
                        st.error("Quiz title bharna zaroori hai.")

        # 2. Edit Existing Quiz Details (Date, Time, Duration)
        with st.expander("✏️ Edit Date, Time & Details of Existing Quiz", expanded=True):
            if quizzes_df.empty:
                st.info("Pehle koi Quiz create karein.")
            else:
                quiz_map = {r['quiz_title']: r['id'] for _, r in quizzes_df.iterrows()}
                edit_q_title = st.selectbox("Select Quiz to Edit:", list(quiz_map.keys()), key="edit_selector")
                edit_q_id = quiz_map[edit_q_title]
                
                conn = get_db()
                q_to_edit = conn.execute("SELECT * FROM quizzes WHERE id = ?", (edit_q_id,)).fetchone()
                conn.close()
                
                try:
                    cur_s_dt = datetime.strptime(q_to_edit['start_datetime'], "%Y-%m-%d %H:%M")
                    cur_e_dt = datetime.strptime(q_to_edit['end_datetime'], "%Y-%m-%d %H:%M")
                except Exception:
                    cur_s_dt = get_ist_now()
                    cur_e_dt = get_ist_now() + timedelta(days=7)

                with st.form(f"edit_quiz_form_{edit_q_id}"):
                    new_edit_title = st.text_input("Quiz Title:", value=q_to_edit['quiz_title'])
                    new_edit_dur = st.number_input("Duration (Minutes):", min_value=1, max_value=300, value=int(q_to_edit['duration_minutes']))
                    
                    ec1, ec2 = st.columns(2)
                    new_s_date = ec1.date_input("Start Date (IST):", value=cur_s_dt.date())
                    new_s_time = ec1.time_input("Start Time (IST):", value=cur_s_dt.time())
                    new_e_date = ec2.date_input("End Date (IST):", value=cur_e_dt.date())
                    new_e_time = ec2.time_input("End Time (IST):", value=cur_e_dt.time())
                    
                    btn_update_quiz = st.form_submit_button("💾 Save Updated Date & Time", type="primary")
                    if btn_update_quiz:
                        up_start_str = f"{new_s_date} {new_s_time.strftime('%H:%M')}"
                        up_end_str = f"{new_e_date} {new_e_time.strftime('%H:%M')}"
                        
                        conn = get_db()
                        conn.execute('''
                            UPDATE quizzes 
                            SET quiz_title = ?, duration_minutes = ?, start_datetime = ?, end_datetime = ?
                            WHERE id = ?
                        ''', (new_edit_title.strip(), new_edit_dur, up_start_str, up_end_str, edit_q_id))
                        conn.commit()
                        conn.close()
                        st.success(f"'{new_edit_title}' successfully update ho gaya!")
                        time.sleep(1)
                        st.rerun()

        st.markdown("---")
        st.write("### Existing Quizzes List & Controls")
        if not quizzes_df.empty:
            for _, r in quizzes_df.iterrows():
                with st.container():
                    st.markdown(f"**{r['quiz_title']}** | Duration: `{r['duration_minutes']} mins` | Status: `{'Active' if r['is_active'] == 1 else 'Disabled'}`")
                    st.markdown(f"🕒 **Valid From (IST):** `{r['start_datetime']}` **To:** `{r['end_datetime']}`")
                    
                    col_q1, col_q2, col_q3 = st.columns([1, 1.5, 1])
                    if col_q1.button(f"Toggle Active ({r['quiz_title']})", key=f"tog_{r['id']}"):
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
                        st.warning(f"Quiz '{r['quiz_title']}' delete kar diya gaya.")
                        time.sleep(1)
                        st.rerun()
                    st.divider()

    # --- SECTION 3: QUESTION BANK ---
    elif admin_tab == "📝 Question Bank (Excel/Manual)":
        st.subheader("Manage Question Bank for Specific Quiz")
        
        if quizzes_df.empty:
            st.info("Pehle ek Quiz create karein.")
        else:
            quiz_options = {row['quiz_title']: row['id'] for _, row in quizzes_df.iterrows()}
            sel_q_title = st.selectbox("Select Quiz:", list(quiz_options.keys()), key="q_quiz")
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
                                ''', (sel_q_id, clean_str(r["question"]), clean_str(r["option_a"]), clean_str(r["option_b"]), clean_str(r["option_c"]), clean_str(r["option_d"]), clean_str(r["correct_option"])))
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

    # --- SECTION 4: STUDENT RESULTS & AUDIT ---
    elif admin_tab == "📊 Student Results & Delete Controls":
        st.subheader("Student Submissions, Scores & Audit Logs")
        
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
                st.info("Is quiz ke liye abhi tak koi submission nahi hai.")
            else:
                st.write("### Batch Performance & Security Audit Log")
                st.dataframe(subs_df, use_container_width=True)
                
                col_d1, col_d2 = st.columns([2, 2])
                with col_d1:
                    csv_data = subs_df.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Download Results (CSV)", data=csv_data, file_name=f"{sel_q_title}_results.csv", mime="text/csv")
                
                with col_d2:
                    if st.button(f"🗑️ Clear ALL Submissions for {sel_q_title}", type="secondary"):
                        conn = get_db()
                        conn.execute("DELETE FROM submissions WHERE quiz_id = ?", (sel_q_id,))
                        conn.execute("DELETE FROM student_responses WHERE quiz_id = ?", (sel_q_id,))
                        conn.commit()
                        conn.close()
                        st.warning(f"Sabhi submissions {sel_q_title} ke liye delete ho gaye.")
                        time.sleep(1)
                        st.rerun()
                
                st.divider()
                st.write("### 🖨️ View, Print or Delete Individual Student Answer Sheet")
                student_display_list = [f"{r['student_name']} (SR: {r['sr_no']})" for _, r in subs_df.iterrows()]
                
                c_sel1, c_sel2 = st.columns([3, 1])
                selected_display = c_sel1.selectbox("Select Student:", student_display_list)
                selected_name = selected_display.split(" (SR: ")[0] if selected_display else ""
                
                if c_sel2.button(f"🗑️ Delete Test"):
                    conn = get_db()
                    conn.execute("DELETE FROM submissions WHERE quiz_id = ? AND student_name = ?", (sel_q_id, selected_name))
                    conn.execute("DELETE FROM student_responses WHERE quiz_id = ? AND student_name = ?", (sel_q_id, selected_name))
                    conn.commit()
                    conn.close()
                    st.warning(f"Student '{selected_name}' ka response delete kar diya gaya.")
                    time.sleep(1)
                    st.rerun()
                
                if selected_name:
                    conn = get_db()
                    ans_df = pd.read_sql_query(
                        "SELECT question_text, selected_option, correct_option, is_correct, recorded_at FROM student_responses WHERE quiz_id = ? AND student_name = ?", 
                        conn, params=(sel_q_id, selected_name)
                    )
                    student_summary = conn.execute(
                        "SELECT student_name, sr_no, score, total_questions, tab_switches, submitted_at FROM submissions WHERE quiz_id = ? AND student_name = ?", 
                        (sel_q_id, selected_name)
                    ).fetchone()
                    conn.close()
                    
                    html_content = f"""
                    <div style="font-family: Arial, sans-serif; border: 2px solid #333; padding: 25px; border-radius: 8px; background-color: #fff; color: #111;">
                        <h2 style="text-align: center; text-transform: uppercase;">Official Assessment Report ({sel_q_title})</h2>
                        <table style="width: 100%; margin-bottom: 20px; font-size: 15px;">
                            <tr>
                                <td><strong>Student Name:</strong> {student_summary['student_name']} | <strong>SR No:</strong> {student_summary['sr_no']}</td>
                                <td style="text-align: right;"><strong>Submitted At:</strong> {student_summary['submitted_at']}</td>
                            </tr>
                            <tr>
                                <td><strong>Score:</strong> <span style="color: green; font-weight: bold;">{student_summary['score']} / {student_summary['total_questions']}</span></td>
                                <td style="text-align: right;"><strong>Tab Switches:</strong> <span style="color: red; font-weight: bold;">{student_summary['tab_switches']} times</span></td>
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

    # --- SECTION 5: FULL DATABASE BACKUP & RESTORE ---
    elif admin_tab == "💾 Full Database Backup & Restore (Excel)":
        st.subheader("💾 Export & Import Complete Portal Data (Excel Backup)")
        
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
        uploaded_backup = st.file_uploader("Upload previous Backup Excel file to restore data:", type=["xlsx"])
        
        if uploaded_backup:
            if st.button("🚀 Restore Complete Data Now"):
                try:
                    excel_file = pd.ExcelFile(uploaded_backup)
                    conn = get_db()
                    cur = conn.cursor()
                    
                    if 'Master_Students' in excel_file.sheet_names:
                        df_stu = pd.read_excel(excel_file, sheet_name='Master_Students')
                        for _, r in df_stu.iterrows():
                            cur.execute("INSERT OR REPLACE INTO master_students (id, student_name, sr_no) VALUES (?, ?, ?)",
                                        (r['id'], clean_str(r['student_name']), clean_str(r['sr_no'])))
                    
                    if 'Quizzes' in excel_file.sheet_names:
                        df_q = pd.read_excel(excel_file, sheet_name='Quizzes')
                        for _, r in df_q.iterrows():
                            cur.execute("INSERT OR REPLACE INTO quizzes (id, quiz_title, duration_minutes, start_datetime, end_datetime, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                                        (r['id'], clean_str(r['quiz_title']), r['duration_minutes'], clean_str(r['start_datetime']), clean_str(r['end_datetime']), r['is_active']))
                    
                    if 'Questions' in excel_file.sheet_names:
                        df_ques = pd.read_excel(excel_file, sheet_name='Questions')
                        for _, r in df_ques.iterrows():
                            cur.execute("INSERT OR REPLACE INTO questions (id, quiz_id, question, option_a, option_b, option_c, option_d, correct_option) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                        (r['id'], r['quiz_id'], clean_str(r['question']), clean_str(r['option_a']), clean_str(r['option_b']), clean_str(r['option_c']), clean_str(r['option_d']), clean_str(r['correct_option'])))
                    
                    if 'Submissions' in excel_file.sheet_names:
                        df_subs = pd.read_excel(excel_file, sheet_name='Submissions')
                        for _, r in df_subs.iterrows():
                            cur.execute("INSERT OR REPLACE INTO submissions (id, quiz_id, student_name, sr_no, score, total_questions, tab_switches, status, submitted_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                        (r['id'], r['quiz_id'], clean_str(r['student_name']), clean_str(r['sr_no']), r['score'], r['total_questions'], r['tab_switches'], clean_str(r['status']), clean_str(r['submitted_at'])))
                    
                    if 'Responses' in excel_file.sheet_names:
                        df_resp = pd.read_excel(excel_file, sheet_name='Responses')
                        for _, r in df_resp.iterrows():
                            cur.execute("INSERT OR REPLACE INTO student_responses (id, quiz_id, student_name, sr_no, question_id, question_text, selected_option, correct_option, is_correct, recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                        (r['id'], r['quiz_id'], clean_str(r['student_name']), clean_str(r['sr_no']), r['question_id'], clean_str(r['question_text']), clean_str(r['selected_option']), clean_str(r['correct_option']), r['is_correct'], clean_str(r['recorded_at'])))
                    
                    conn.commit()
                    conn.close()
                    st.success("✅ Sara data successfully restore ho gaya!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Restore failed: {e}")

# ==========================================
# 5. STUDENT EXAM PORTAL (Robust Clean Match Login)
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
                in_name = st.text_input("Student Name (Registered):", placeholder="e.g. Shashank Verma")
                in_pwd = st.text_input("Password (Aapka SR No):", type="password")
                
                submit_login = st.form_submit_button("Enter Exam Portal", type="primary")
                
                if submit_login:
                    q_id = quiz_opts[sel_quiz_title]
                    clean_name = clean_str(in_name)
                    clean_pwd = clean_str(in_pwd)
                    
                    conn = get_db()
                    q_data = conn.execute("SELECT * FROM quizzes WHERE id = ?", (q_id,)).fetchone()
                    
                    # Fuzzy / Case-Insensitive Name & SR match
                    all_students = conn.execute("SELECT student_name, sr_no FROM master_students").fetchall()
                    conn.close()
                    
                    matched_student = None
                    for s in all_students:
                        db_name = clean_str(s['student_name'])
                        db_sr = clean_str(s['sr_no'])
                        if db_name.lower() == clean_name.lower():
                            matched_student = (db_name, db_sr)
                            break
                    
                    now_ist = get_ist_now().replace(tzinfo=None)
                    try:
                        start_dt = datetime.strptime(q_data['start_datetime'], "%Y-%m-%d %H:%M")
                        end_dt = datetime.strptime(q_data['end_datetime'], "%Y-%m-%d %H:%M")
                    except Exception:
                        start_dt = now_ist - timedelta(days=1)
                        end_dt = now_ist + timedelta(days=10)
                    
                    if not clean_name or not clean_pwd:
                        st.error("Kripya Naam aur Password (SR No) dono darj karein.")
                    elif not matched_student:
                        st.error(f"❌ Student Name '{clean_name}' master list me nahi mila! Kripya sahi spelling dalein.")
                    elif matched_student[1] != clean_pwd:
                        st.error("Galat Password! (Password aapka SR Number hai).")
                    elif now_ist < start_dt:
                        st.error(f"⏳ Exam abhi shuru nahi hua hai! Start Time (IST): {q_data['start_datetime']}")
                    elif now_ist > end_dt:
                        st.error(f"⏰ Exam ka samay samapt ho chuka hai! End Time (IST): {q_data['end_datetime']}")
                    else:
                        st.session_state.student_name = matched_student[0]
                        st.session_state.student_sr = matched_student[1]
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

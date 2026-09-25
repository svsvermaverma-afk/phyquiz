import streamlit as st
import sqlite3
import pandas as pd
import time
import io
import os
import re
from datetime import datetime, timedelta, timezone
import streamlit.components.v1 as components

# PDF Generation Libraries (Merit List)
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ==========================================
# 1. PAGE CONFIGURATION & RESPONSIVE CSS
# ==========================================
st.set_page_config(
    page_title="ABIC Renukoot - Physics Quiz Portal",
    page_icon="⚛️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    /* Top Banner Styling */
    .school-header {
        text-align: center;
        padding: 14px 10px;
        margin-bottom: 20px;
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        color: white;
        border-radius: 12px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.15);
    }
    .school-header h1 {
        margin: 0;
        font-size: 2rem !important;
        font-weight: 800;
        letter-spacing: 1px;
        color: #ffffff !important;
    }
    .school-header h3 {
        margin: 5px 0;
        font-size: 1.25rem !important;
        font-weight: 600;
        color: #f1f5f9 !important;
    }
    .school-header p {
        margin: 4px 0 0 0;
        font-size: 1rem;
        color: #e2e8f0;
    }

    /* Mobile Responsive Optimizations */
    @media only screen and (max-width: 768px) {
        .block-container {
            padding-top: 1rem !important;
            padding-left: 0.8rem !important;
            padding-right: 0.8rem !important;
            padding-bottom: 2rem !important;
        }
        .school-header h1 { font-size: 1.4rem !important; }
        .school-header h3 { font-size: 1rem !important; }
        .school-header p { font-size: 0.88rem !important; }
        .stButton>button {
            width: 100% !important;
            padding: 12px 16px !important;
            font-size: 16px !important;
            margin-bottom: 8px !important;
        }
        .stRadio > div { gap: 10px !important; }
        [data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
        }
    }
    @media only screen and (min-width: 769px) {
        .block-container { padding-top: 1.5rem !important; }
    }
</style>
""", unsafe_allow_html=True)

# Top School & Teacher Header Banner
st.markdown("""
<div class="school-header">
    <h1>ABIC RENUKOOT</h1>
    <h3>⚡ Physics Subject Quiz Portal ⚡</h3>
    <p>Mentor: <b>Shashank Verma, TGT (Physics)</b></p>
</div>
""", unsafe_allow_html=True)

DB_FILE = "master_quiz_system_prod_v17.db"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@2026"

STUDENTS_FILE = "students.xlsx"
Q11_FILE = "questions_11.xlsx"
Q12_FILE = "questions_12.xlsx"

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

# Smart Answer Matcher Engine
def is_answer_correct(selected, correct, opt_a, opt_b, opt_c, opt_d):
    if not selected:
        return False
    s = clean_text(selected).strip().lower()
    c = clean_text(correct).strip().lower()
    a = clean_text(opt_a).strip().lower()
    b = clean_text(opt_b).strip().lower()
    c_opt = clean_text(opt_c).strip().lower()
    d = clean_text(opt_d).strip().lower()
    
    # Direct Match
    if s == c:
        return True
    
    # Letter & Index Mapping
    mapping = {
        'a': a, 'option a': a, '(a)': a, '1': a,
        'b': b, 'option b': b, '(b)': b, '2': b,
        'c': c_opt, 'option c': c_opt, '(c)': c_opt, '3': c_opt,
        'd': d, 'option d': d, '(d)': d, '4': d
    }
    
    if c in mapping and s == mapping[c]:
        return True
    return False

# ==========================================
# 2. DATABASE MANAGEMENT & AUTO-SYNC
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
        CREATE TABLE IF NOT EXISTS master_students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            sr_no TEXT NOT NULL,
            normalized_name TEXT UNIQUE NOT NULL
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_class TEXT NOT NULL,
            topic TEXT NOT NULL,
            quiz_title TEXT UNIQUE NOT NULL,
            duration_minutes INTEGER DEFAULT 15,
            start_datetime TEXT NOT NULL,
            end_datetime TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    try:
        c.execute("ALTER TABLE quizzes ADD COLUMN target_class TEXT DEFAULT 'Class 11'")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE quizzes ADD COLUMN topic TEXT DEFAULT 'General Physics'")
    except sqlite3.OperationalError:
        pass

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

    c.execute('''
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            quiz_id INTEGER NOT NULL,
            normalized_name TEXT NOT NULL,
            start_epoch REAL NOT NULL,
            PRIMARY KEY(quiz_id, normalized_name)
        )
    ''')
    
    now_time = get_ist_now() - timedelta(hours=1)
    default_start = now_time.strftime("%Y-%m-%d %H:%M")
    default_end = (now_time + timedelta(days=30)).strftime("%Y-%m-%d %H:%M")
    
    c.execute('''
        INSERT OR IGNORE INTO quizzes (target_class, topic, quiz_title, duration_minutes, start_datetime, end_datetime, is_active)
        VALUES (?, ?, ?, ?, ?, ?, 1)
    ''', ("Class 11", "Laws of Motion & Work Energy", "Class 11 - Physics Exam", 15, default_start, default_end))
    
    c.execute('''
        INSERT OR IGNORE INTO quizzes (target_class, topic, quiz_title, duration_minutes, start_datetime, end_datetime, is_active)
        VALUES (?, ?, ?, ?, ?, ?, 1)
    ''', ("Class 12", "Electrostatics & Magnetism", "Class 12 - Physics Exam", 20, default_start, default_end))
    
    c.execute("SELECT id FROM quizzes WHERE quiz_title = ?", ("Class 11 - Physics Exam",))
    q11_row = c.fetchone()
    q11_id = q11_row[0] if q11_row else 1
    
    c.execute("SELECT id FROM quizzes WHERE quiz_title = ?", ("Class 12 - Physics Exam",))
    q12_row = c.fetchone()
    q12_id = q12_row[0] if q12_row else 2

    # Load Students
    for s_path in [STUDENTS_FILE, "students.csv"]:
        if os.path.exists(s_path):
            try:
                s_df = pd.read_csv(s_path) if s_path.endswith(".csv") else pd.read_excel(s_path)
                s_df.columns = [str(col).strip().lower().replace(" ", "_") for col in s_df.columns]
                n_col = next((col for col in s_df.columns if col in ["name", "student_name", "student", "studentname"]), s_df.columns[0])
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

    # Load Questions Class 11
    for q11_path in [Q11_FILE, "questions_11.csv"]:
        if os.path.exists(q11_path):
            try:
                df11 = pd.read_csv(q11_path) if q11_path.endswith(".csv") else pd.read_excel(q11_path)
                df11.columns = [str(col).strip().lower().replace(" ", "_") for col in df11.columns]
                c.execute("SELECT COUNT(*) FROM questions WHERE quiz_id = ?", (q11_id,))
                if c.fetchone()[0] == 0:
                    for _, row in df11.iterrows():
                        if pd.notna(row["question"]) and pd.notna(row["correct_option"]):
                            c.execute('''
                                INSERT INTO questions (quiz_id, question, option_a, option_b, option_c, option_d, correct_option)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''', (q11_id, str(row["question"]).strip(), str(row["option_a"]).strip(), str(row["option_b"]).strip(), str(row["option_c"]).strip(), str(row["option_d"]).strip(), str(row["correct_option"]).strip()))
            except Exception:
                pass

    # Load Questions Class 12
    for q12_path in [Q12_FILE, "questions_12.csv"]:
        if os.path.exists(q12_path):
            try:
                df12 = pd.read_csv(q12_path) if q12_path.endswith(".csv") else pd.read_excel(q12_path)
                df12.columns = [str(col).strip().lower().replace(" ", "_") for col in df12.columns]
                c.execute("SELECT COUNT(*) FROM questions WHERE quiz_id = ?", (q12_id,))
                if c.fetchone()[0] == 0:
                    for _, row in df12.iterrows():
                        if pd.notna(row["question"]) and pd.notna(row["correct_option"]):
                            c.execute('''
                                INSERT INTO questions (quiz_id, question, option_a, option_b, option_c, option_d, correct_option)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''', (q12_id, str(row["question"]).strip(), str(row["option_a"]).strip(), str(row["option_b"]).strip(), str(row["option_c"]).strip(), str(row["option_d"]).strip(), str(row["correct_option"]).strip()))
            except Exception:
                pass

    conn.commit()
    conn.close()

init_db()

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

def get_or_set_attempt_start(quiz_id, student_norm_name):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT start_epoch FROM quiz_attempts WHERE quiz_id = ? AND normalized_name = ?", (quiz_id, student_norm_name))
    row = c.fetchone()
    if row:
        start_epoch = row["start_epoch"]
    else:
        start_epoch = time.time()
        c.execute("INSERT OR REPLACE INTO quiz_attempts (quiz_id, normalized_name, start_epoch) VALUES (?, ?, ?)", (quiz_id, student_norm_name, start_epoch))
        conn.commit()
    conn.close()
    return start_epoch

# ==========================================
# PDF MERIT LIST GENERATOR
# ==========================================
def generate_merit_pdf(subs_df, quiz_info):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('SchoolTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=18, leading=22, alignment=1, textColor=colors.HexColor("#1e3c72"))
    subtitle_style = ParagraphStyle('SubTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=13, leading=16, alignment=1, textColor=colors.HexColor("#333333"))
    meta_style = ParagraphStyle('Meta', parent=styles['Normal'], fontName='Helvetica', fontSize=10, leading=14, alignment=1, textColor=colors.HexColor("#555555"))
    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=11, alignment=1)
    cell_bold = ParagraphStyle('CellBold', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=11, alignment=1)
    
    elements = []
    elements.append(Paragraph("ABIC RENUKOOT", title_style))
    elements.append(Paragraph("Merit List & Student Performance Report", subtitle_style))
    elements.append(Paragraph(f"<b>Exam:</b> {quiz_info.get('quiz_title', 'Exam')} | <b>Class:</b> {quiz_info.get('target_class', '')} | <b>Topic:</b> {quiz_info.get('topic', '')}", meta_style))
    elements.append(Paragraph(f"Mentor: <b>Shashank Verma, TGT (Physics)</b> | Generated on: {get_ist_now().strftime('%d-%b-%Y %I:%M %p')}", meta_style))
    elements.append(Spacer(1, 15))
    
    table_data = [
        [Paragraph("<b>Rank</b>", cell_bold), Paragraph("<b>Student Name</b>", cell_bold), Paragraph("<b>SR No</b>", cell_bold), Paragraph("<b>Score</b>", cell_bold), Paragraph("<b>Percentage</b>", cell_bold), Paragraph("<b>Switches</b>", cell_bold), Paragraph("<b>Submitted At</b>", cell_bold)]
    ]
    
    for idx, row in subs_df.iterrows():
        rank = idx + 1
        pct = (row['score'] / row['total_questions'] * 100) if row['total_questions'] > 0 else 0
        rank_str = f"🥇 Rank {rank}" if rank == 1 else (f"🥈 Rank {rank}" if rank == 2 else (f"🥉 Rank {rank}" if rank == 3 else f"{rank}"))
        table_data.append([
            Paragraph(rank_str, cell_bold if rank <= 3 else cell_style),
            Paragraph(str(row['student_name']), cell_style),
            Paragraph(str(row['sr_no']), cell_style),
            Paragraph(f"{row['score']} / {row['total_questions']}", cell_bold),
            Paragraph(f"{pct:.1f}%", cell_style),
            Paragraph(str(row['tab_switches']), cell_style),
            Paragraph(str(row['submitted_at']), cell_style)
        ])
    
    col_widths = [65, 130, 65, 65, 60, 50, 100]
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e3c72")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#dcdcdc")),
    ]
    
    for r_idx in range(1, len(table_data)):
        if r_idx == 1:
            t_style.append(('BACKGROUND', (0, r_idx), (-1, r_idx), colors.HexColor("#fff9db")))
        elif r_idx == 2:
            t_style.append(('BACKGROUND', (0, r_idx), (-1, r_idx), colors.HexColor("#f1f3f5")))
        elif r_idx == 3:
            t_style.append(('BACKGROUND', (0, r_idx), (-1, r_idx), colors.HexColor("#fff4e6")))
        elif r_idx % 2 == 0:
            t_style.append(('BACKGROUND', (0, r_idx), (-1, r_idx), colors.HexColor("#f8f9fa")))
            
    t.setStyle(TableStyle(t_style))
    elements.append(t)
    doc.build(elements)
    pdf_val = buffer.getvalue()
    buffer.close()
    return pdf_val

# Anti-Cheating & Live Timer Component (Responsive)
def inject_live_timer_and_security(remaining_seconds, quiz_id, student_name):
    timer_js = f"""
    <style>
        #sticky-timer-box {{
            position: fixed; 
            top: 50px; 
            right: 20px; 
            background: #ff4b4b; 
            color: #ffffff; 
            padding: 10px 18px; 
            border-radius: 8px; 
            font-family: monospace; 
            font-size: 18px; 
            font-weight: bold; 
            z-index: 999999;
            box-shadow: 0 4px 12px rgba(0,0,0,0.25);
            border: 2px solid white;
        }}
        @media only screen and (max-width: 600px) {{
            #sticky-timer-box {{
                top: 40px;
                right: 8px;
                padding: 6px 12px;
                font-size: 14px;
            }}
        }}
    </style>
    <div id="sticky-timer-box">
        ⏳ <span id="timer-display">Loading...</span> | ⚠️ <span id="switch-count">0</span>
    </div>

    <script>
    let timeLeft = {int(remaining_seconds)};
    let display = document.getElementById('timer-display');
    let switchCountElem = document.getElementById('switch-count');
    let tabSwitches = sessionStorage.getItem('tab_switches_{quiz_id}_{student_name}') || 0;
    switchCountElem.innerHTML = tabSwitches;

    function triggerAutoSubmit() {{
        let buttons = window.parent.document.querySelectorAll('button');
        buttons.forEach(btn => {{
            if (btn.innerText.includes("Submit Final Answers")) {{ btn.click(); }}
        }});
    }}

    function updateTimer() {{
        if (timeLeft <= 0) {{
            display.innerHTML = "TIME UP!";
            triggerAutoSubmit();
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
        alert('⚠️ WARNING (' + tabSwitches + '/3): Tab switch detected! Repeated tab switching will result in automatic submission.');
        if (tabSwitches >= 3) {{
            alert('❌ Maximum limit reached. The test is now being submitted automatically.');
            triggerAutoSubmit();
        }}
    }});

    document.addEventListener('contextmenu', function(e) {{ e.preventDefault(); }});
    document.addEventListener('copy', function(e) {{ e.preventDefault(); }});
    document.addEventListener('cut', function(e) {{ e.preventDefault(); }});
    document.addEventListener('paste', function(e) {{ e.preventDefault(); }});
    </script>
    """
    components.html(timer_js, height=65)

# ==========================================
# 3. SIDEBAR NAVIGATION
# ==========================================
st.sidebar.title("🧭 Navigation")
selected_portal = st.sidebar.radio("Select Portal:", ["🎓 Student Exam Portal", "⚙️ Admin Control Center"])
st.sidebar.divider()

# ==========================================
# 4. ADMIN CONTROL PANEL
# ==========================================
if selected_portal == "⚙️ Admin Control Center":
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False

    if not st.session_state.admin_authenticated:
        st.title("🔐 Admin Login Portal")
        st.markdown("Authorized teacher/admin access only.")
        col1, _ = st.columns([1.2, 1])
        with col1:
            with st.form("admin_login_form"):
                in_user = st.text_input("Admin Username:")
                in_pass = st.text_input("Admin Password:", type="password")
                btn_login = st.form_submit_button("Sign In as Admin", type="primary")
                if btn_login:
                    if in_user.strip() == ADMIN_USERNAME and in_pass.strip() == ADMIN_PASSWORD:
                        st.session_state.admin_authenticated = True
                        st.success("Admin login successful!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Invalid Username or Password! Access Denied.")
        st.stop()

    st.sidebar.success(f"👑 Logged in as: `{ADMIN_USERNAME}`")
    if st.sidebar.button("Log Out Admin"):
        st.session_state.admin_authenticated = False
        st.rerun()

    st.title("⚙️ Teacher & Examination Control Center")
    st.info(f"🕒 Current Indian Standard Time (IST): **{get_ist_now().strftime('%Y-%m-%d %I:%M %p')}**")

    quizzes_df = get_all_quizzes()
    admin_tab = st.selectbox("Select Management Section:", [
        "📚 Create & Manage Quizzes (Class & Topic Controls)", 
        "👥 Master Student Directory (Excel/Manual)", 
        "📝 Question Bank (Excel/Manual)",
        "📊 Student Results & Controls", 
        "💾 Full Database Backup & Restore (Excel)"
    ])

    st.divider()

    # SECTION 1: CREATE & MANAGE QUIZZES
    if admin_tab == "📚 Create & Manage Quizzes (Class & Topic Controls)":
        st.subheader("Existing Quizzes & Controls")
        with st.expander("➕ Create New Quiz", expanded=False):
            with st.form("new_quiz_form"):
                c_cls1, c_cls2 = st.columns(2)
                target_class_choice = c_cls1.selectbox("Select Class:", ["Class 11", "Class 12", "Class 9", "Class 10", "Other"])
                topic_name = c_cls2.text_input("Topic / Chapter Name (e.g., Kinematics):", value="Units & Measurement")
                q_title = st.text_input("Quiz Title:", value=f"{target_class_choice} - {topic_name}")
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
                    c_top = clean_text(topic_name)
                    if c_title:
                        try:
                            conn = get_db()
                            c = conn.cursor()
                            c.execute('''
                                INSERT INTO quizzes (target_class, topic, quiz_title, duration_minutes, start_datetime, end_datetime, is_active)
                                VALUES (?, ?, ?, ?, ?, ?, 1)
                            ''', (target_class_choice, c_top, c_title, q_dur, start_str, end_str))
                            conn.commit()
                            conn.close()
                            st.success(f"Quiz '{c_title}' created successfully!")
                            time.sleep(1)
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("A quiz with this title already exists.")

        st.markdown("---")
        if not quizzes_df.empty:
            for _, r in quizzes_df.iterrows():
                with st.container():
                    st.markdown(f"### 📝 **{r['quiz_title']}**")
                    cls_val = r['target_class'] if 'target_class' in r and pd.notna(r['target_class']) else 'Class 11'
                    top_val = r['topic'] if 'topic' in r and pd.notna(r['topic']) else 'General Physics'
                    st.markdown(f"🏷️ **Class:** `{cls_val}` | 📖 **Topic:** `{top_val}`")
                    st.markdown(f"⏱️ **Duration:** `{r['duration_minutes']} mins` | **Status:** `{'Active' if r['is_active'] == 1 else 'Disabled'}`")
                    st.markdown(f"🕒 **Valid From:** `{r['start_datetime']}` **To:** `{r['end_datetime']}`")
                    
                    col_b1, col_b2, col_b3 = st.columns([1.5, 1.5, 1])
                    if col_b1.button(f"Toggle Active ({r['quiz_title']})", key=f"tog_{r['id']}"):
                        new_status = 0 if r['is_active'] == 1 else 1
                        conn = get_db()
                        conn.execute("UPDATE quizzes SET is_active = ? WHERE id = ?", (new_status, r['id']))
                        conn.commit()
                        conn.close()
                        st.rerun()
                    
                    if col_b2.button(f"⚡ Start NOW (Instant Live)", key=f"now_{r['id']}"):
                        now_start = (get_ist_now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
                        now_end = (get_ist_now() + timedelta(days=10)).strftime("%Y-%m-%d %H:%M")
                        conn = get_db()
                        conn.execute("UPDATE quizzes SET start_datetime = ?, end_datetime = ?, is_active = 1 WHERE id = ?", (now_start, now_end, r['id']))
                        conn.commit()
                        conn.close()
                        st.success("Quiz is now LIVE immediately!")
                        time.sleep(1)
                        st.rerun()
                    
                    if col_b3.button(f"🗑️ Delete Quiz", key=f"del_quiz_{r['id']}", type="secondary"):
                        conn = get_db()
                        conn.execute("DELETE FROM quizzes WHERE id = ?", (r['id'],))
                        conn.commit()
                        conn.close()
                        st.warning("Quiz deleted.")
                        time.sleep(1)
                        st.rerun()

                    with st.expander(f"📅 Edit Details: {r['quiz_title']}", expanded=False):
                        try:
                            cur_s_dt = datetime.strptime(r['start_datetime'], "%Y-%m-%d %H:%M")
                            cur_e_dt = datetime.strptime(r['end_datetime'], "%Y-%m-%d %H:%M")
                        except Exception:
                            cur_s_dt = get_ist_now()
                            cur_e_dt = get_ist_now() + timedelta(days=7)

                        with st.form(f"quick_edit_quiz_{r['id']}"):
                            ce1, ce2 = st.columns(2)
                            class_options = ["Class 11", "Class 12", "Class 9", "Class 10", "Other"]
                            cur_cls_idx = class_options.index(cls_val) if cls_val in class_options else 0
                            ed_cls = ce1.selectbox("Class:", class_options, index=cur_cls_idx, key=f"cls_{r['id']}")
                            ed_topic = ce2.text_input("Topic / Chapter Name:", value=top_val, key=f"top_{r['id']}")
                            ed_title = st.text_input("Quiz Title:", value=r['quiz_title'], key=f"t_{r['id']}")
                            ed_dur = st.number_input("Exam Duration (Minutes):", min_value=1, max_value=300, value=int(r['duration_minutes']), key=f"d_{r['id']}")
                            c1, c2 = st.columns(2)
                            ed_s_date = c1.date_input("Start Date (IST):", value=cur_s_dt.date(), key=f"sd_{r['id']}")
                            ed_s_time = c1.time_input("Start Time (IST):", value=cur_s_dt.time(), key=f"st_{r['id']}")
                            ed_e_date = c2.date_input("End Date (IST):", value=cur_e_dt.date(), key=f"ed_{r['id']}")
                            ed_e_time = c2.time_input("End Time (IST):", value=cur_e_dt.time(), key=f"et_{r['id']}")
                            
                            if st.form_submit_button("💾 Save Changes", type="primary"):
                                new_start_str = f"{ed_s_date} {ed_s_time.strftime('%H:%M')}"
                                new_end_str = f"{ed_e_date} {ed_e_time.strftime('%H:%M')}"
                                conn = get_db()
                                conn.execute('''
                                    UPDATE quizzes 
                                    SET target_class = ?, topic = ?, quiz_title = ?, duration_minutes = ?, start_datetime = ?, end_datetime = ?
                                    WHERE id = ?
                                ''', (ed_cls, clean_text(ed_topic), clean_text(ed_title), ed_dur, new_start_str, new_end_str, r['id']))
                                conn.commit()
                                conn.close()
                                st.success(f"'{ed_title}' updated successfully!")
                                time.sleep(1)
                                st.rerun()
                    st.divider()
        else:
            st.info("No quizzes created yet. Use the button above to create one.")

    # SECTION 2: MASTER STUDENTS
    elif admin_tab == "👥 Master Student Directory (Excel/Manual)":
        st.subheader("👥 Master Student Directory")
        st.markdown("**Tip:** You can keep `students.xlsx` (`name`, `sr_no`) in the repository for permanent automatic loading.")
        with st.expander("📂 Bulk Upload via Web", expanded=True):
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
                        st.success(f"Successfully imported {added_cnt} students!")
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
            st.info("No registered students found.")
        else:
            st.write(f"Total Enrolled: **{len(master_df)} Students**")
            st.dataframe(master_df, use_container_width=True)

    # SECTION 3: QUESTION BANK (Fixed Error Here)
    elif admin_tab == "📝 Question Bank (Excel/Manual)":
        st.subheader("Question Bank Management")
        st.markdown("**Tip:** Uploading `questions_11.xlsx` and `questions_12.xlsx` to the repository will automatically populate questions.")
        if quizzes_df.empty:
            st.info("Please create a quiz first.")
        else:
            quiz_options = {f"[{r.get('target_class','Class 11') if 'target_class' in r else 'Class 11'}] {r['quiz_title']} ({r.get('topic','General') if 'topic' in r else 'General'})": r['id'] for _, r in quizzes_df.iterrows()}
            sel_q_label = st.selectbox("Select Quiz:", list(quiz_options.keys()), key="q_quiz")
            sel_q_id = quiz_options[sel_q_label]
            
            with st.expander("📂 Bulk Upload Questions via Web", expanded=True):
                st.markdown("Required Columns: `question`, `option_a`, `option_b`, `option_c`, `option_d`, `correct_option`")
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
                                ''', (
                                    sel_q_id, 
                                    str(r["question"]).strip(), 
                                    str(r["option_a"]).strip(), 
                                    str(r["option_b"]).strip(), 
                                    str(r["option_c"]).strip(),  # Fixed variable here
                                    str(r["option_d"]).strip(), 
                                    str(r["correct_option"]).strip()
                                ))
                                cnt += 1
                            conn.commit()
                            conn.close()
                            st.success(f"{cnt} questions imported successfully!")
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
                st.markdown(f"🎯 **Correct Answer:** `{row['correct_option']}`")
                if st.button(f"Delete Q{idx+1}", key=f"del_q_{row['id']}"):
                    conn = get_db()
                    conn.execute("DELETE FROM questions WHERE id = ?", (row['id'],))
                    conn.commit()
                    conn.close()
                    st.rerun()
                st.divider()

    # SECTION 4: STUDENT RESULTS & MERIT PDF
    elif admin_tab == "📊 Student Results & Controls":
        st.subheader("Student Submissions & Performance Sheet")
        if quizzes_df.empty:
            st.info("Please create a quiz first.")
        else:
            quiz_options = {f"[{r.get('target_class','Class 11') if 'target_class' in r else 'Class 11'}] {r['quiz_title']} ({r.get('topic','General') if 'topic' in r else 'General'})": r['id'] for _, r in quizzes_df.iterrows()}
            sel_q_label = st.selectbox("Select Quiz to View Results:", list(quiz_options.keys()))
            sel_q_id = quiz_options[sel_q_label]
            
            conn = get_db()
            quiz_info_row = conn.execute("SELECT * FROM quizzes WHERE id = ?", (sel_q_id,)).fetchone()
            quiz_meta = dict(quiz_info_row) if quiz_info_row else {}
            
            # Recalculate Previous 0 Scores Automatically
            try:
                resp_rows = conn.execute('''
                    SELECT r.id, r.selected_option, r.correct_option, q.option_a, q.option_b, q.option_c, q.option_d, r.sr_no
                    FROM student_responses r
                    JOIN questions q ON r.question_id = q.id
                    WHERE r.quiz_id = ?
                ''', (sel_q_id,)).fetchall()
                
                for rr in resp_rows:
                    is_corr = 1 if is_answer_correct(rr['selected_option'], rr['correct_option'], rr['option_a'], rr['option_b'], rr['option_c'], rr['option_d']) else 0
                    conn.execute("UPDATE student_responses SET is_correct = ? WHERE id = ?", (is_corr, rr['id']))
                
                conn.execute('''
                    UPDATE submissions
                    SET score = (
                        SELECT COALESCE(SUM(is_correct), 0)
                        FROM student_responses 
                        WHERE student_responses.quiz_id = submissions.quiz_id 
                          AND student_responses.sr_no = submissions.sr_no
                    )
                    WHERE quiz_id = ?
                ''', (sel_q_id,))
                conn.commit()
            except Exception:
                pass
            
            try:
                subs_df = pd.read_sql_query(
                    "SELECT student_name, sr_no, score, total_questions, tab_switches, status, submitted_at FROM submissions WHERE quiz_id = ? ORDER BY score DESC, submitted_at ASC", 
                    conn, params=(sel_q_id,)
                )
            except Exception:
                subs_df = pd.DataFrame()
            conn.close()
            
            if subs_df.empty:
                st.info("No submissions found for this quiz.")
            else:
                subs_df_display = subs_df.copy()
                subs_df_display.insert(0, "Rank", range(1, len(subs_df_display) + 1))
                
                st.write("### 🏆 Merit List (Ranked from Highest to Lowest Score)")
                st.dataframe(subs_df_display, use_container_width=True)
                
                c_d1, c_d2 = st.columns([1, 1])
                with c_d1:
                    pdf_bytes = generate_merit_pdf(subs_df, quiz_meta)
                    st.download_button(
                        label="📄 Download Official Merit List (PDF)",
                        data=pdf_bytes,
                        file_name=f"Merit_List_{quiz_meta.get('quiz_title','Exam').replace(' ', '_')}_{get_ist_now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                        type="primary"
                    )
                with c_d2:
                    csv_data = subs_df_display.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download Results (CSV)",
                        data=csv_data,
                        file_name=f"results_{sel_q_id}.csv",
                        mime="text/csv"
                    )
                
                st.divider()
                if st.button(f"🗑️ Clear ALL Submissions for this Quiz", type="secondary"):
                    conn = get_db()
                    conn.execute("DELETE FROM submissions WHERE quiz_id = ?", (sel_q_id,))
                    conn.execute("DELETE FROM student_responses WHERE quiz_id = ?", (sel_q_id,))
                    conn.execute("DELETE FROM quiz_attempts WHERE quiz_id = ?", (sel_q_id,))
                    conn.commit()
                    conn.close()
                    st.warning("All submissions and attempt timers cleared.")
                    time.sleep(1)
                    st.rerun()

    # SECTION 5: BACKUP & RESTORE
    elif admin_tab == "💾 Full Database Backup & Restore (Excel)":
        st.subheader("💾 Full Database Backup & Restore")
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
                            target_c = r['target_class'] if 'target_class' in r and pd.notna(r['target_class']) else 'Class 11'
                            top_c = r['topic'] if 'topic' in r and pd.notna(r['topic']) else 'General Physics'
                            cur.execute("INSERT OR REPLACE INTO quizzes (id, target_class, topic, quiz_title, duration_minutes, start_datetime, end_datetime, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                        (r['id'], target_c, top_c, clean_text(r['quiz_title']), r['duration_minutes'], r['start_datetime'], r['end_datetime'], r['is_active']))
                    
                    if 'Questions' in excel_file.sheet_names:
                        df_ques = pd.read_excel(excel_file, sheet_name='Questions')
                        for _, r in df_ques.iterrows():
                            cur.execute("INSERT OR REPLACE INTO questions (id, quiz_id, question, option_a, option_b, option_c, option_d, correct_option) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                        (r['id'], r['quiz_id'], r['question'], r['option_a'], r['option_b'], r['option_c'], r['option_d'], r['correct_option']))
                    
                    if 'Submissions' in excel_file.sheet_names:
                        df_subs = pd.read_excel(excel_file, sheet_name='Submissions')
                        for _, r in df_subs.iterrows():
                            cur.execute("INSERT OR REPLACE INTO submissions (id, quiz_id, student_name, sr_no, score, total_questions, tab_switches, status, submitted_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                        (r['id'], r['quiz_id'], clean_text(r['student_name']), clean_sr_no(r['sr_no']), r['score'], r['total_questions'], r['tab_switches'], r['status'], r['submitted_at']))
                    
                    if 'Responses' in excel_file.sheet_names:
                        df_resp = pd.read_excel(excel_file, sheet_name='Responses')
                        for _, r in df_resp.iterrows():
                            cur.execute("INSERT OR REPLACE INTO student_responses (id, quiz_id, student_name, sr_no, question_id, question_text, selected_option, correct_option, is_correct, recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                        (r['id'], r['quiz_id'], clean_text(r['student_name']), clean_sr_no(r['sr_no']), r['question_id'], r['question_text'], r['selected_option'], r['correct_option'], r['is_correct'], r['recorded_at']))
                    
                    conn.commit()
                    conn.close()
                    st.success("✅ All data restored successfully!")
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

    quizzes_df = get_all_quizzes()
    active_quizzes = quizzes_df[quizzes_df['is_active'] == 1] if not quizzes_df.empty else pd.DataFrame()

    if active_quizzes.empty:
        st.error("🛑 No exams are currently active. Please contact your subject teacher.")
        st.stop()

    # Student Login Form
    if not st.session_state.student_name or not st.session_state.selected_quiz_id:
        st.subheader("🎓 Student Examination Login Portal")
        st.markdown("Select your Quiz/Topic, enter your **Registered Full Name** and your **SR No** as Password.")
        
        quiz_opts = {}
        for _, row in active_quizzes.iterrows():
            cls_t = row['target_class'] if 'target_class' in row and pd.notna(row['target_class']) else 'Class'
            top_t = row['topic'] if 'topic' in row and pd.notna(row['topic']) else 'General'
            label = f"[{cls_t}] {row['quiz_title']} • (Topic: {top_t})"
            quiz_opts[label] = row['id']
        
        col1, _ = st.columns([1.2, 1])
        with col1:
            with st.form("student_login_form"):
                sel_quiz_label = st.selectbox("Select Quiz / Topic:", list(quiz_opts.keys()))
                in_name = st.text_input("Student Name (Registered):", placeholder="Enter your full name")
                in_pwd = st.text_input("Password (Your SR No):", type="password")
                submit_login = st.form_submit_button("Enter Exam Portal", type="primary")
                
                if submit_login:
                    q_id = quiz_opts[sel_quiz_label]
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
                        st.error("Please enter both Name and Password (SR No).")
                    elif not student_data:
                        st.error(f"❌ Student Name '{clean_input_name}' is not registered! Please verify spelling.")
                    elif clean_sr_no(student_data['sr_no']) != clean_input_pwd:
                        st.error("Incorrect Password! (Your password is your SR Number).")
                    elif now_ist < start_dt:
                        st.error(f"⏳ Exam has not started yet! Start Time (IST): {q_data['start_datetime']}")
                    elif now_ist > end_dt:
                        st.error(f"⏰ Exam window has expired! End Time (IST): {q_data['end_datetime']}")
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
    quiz_row = conn.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
    conn.close()

    quiz_dict = dict(quiz_row) if quiz_row else {}
    quiz_title_val = quiz_dict.get('quiz_title', 'Exam')
    quiz_topic_val = quiz_dict.get('topic', 'General')
    quiz_class_val = quiz_dict.get('target_class', 'Class 11')
    quiz_dur_val = int(quiz_dict.get('duration_minutes', 15))

    st.sidebar.markdown(f"**Candidate:** `{student_name}`")
    st.sidebar.markdown(f"**SR No:** `{student_sr}`")
    st.sidebar.markdown(f"**Exam:** `{quiz_title_val}`")
    st.sidebar.markdown(f"**Topic:** `{quiz_topic_val}`")

    if st.sidebar.button("Log Out"):
        st.session_state.student_name = None
        st.session_state.student_sr = None
        st.session_state.selected_quiz_id = None
        st.rerun()

    st.title(f"📝 {quiz_title_val}")
    st.markdown(f"##### 📖 Topic: **{quiz_topic_val}** | Class: **{quiz_class_val}**")

    # Full Detailed Scorecard
    conn = get_db()
    sub_check = conn.execute("SELECT * FROM submissions WHERE quiz_id = ? AND LOWER(student_name) = ?", (quiz_id, student_name.lower())).fetchone()
    conn.close()

    if sub_check:
        st.success(f"✅ {student_name}, your exam has been successfully submitted!")
        
        c_m1, c_m2, c_m3 = st.columns(3)
        c_m1.metric("Final Score", f"{sub_check['score']} / {sub_check['total_questions']}")
        pct = (sub_check['score'] / sub_check['total_questions'] * 100) if sub_check['total_questions'] > 0 else 0
        c_m2.metric("Percentage", f"{pct:.1f}%")
        c_m3.metric("Tab Switches Recorded", f"{sub_check['tab_switches']} times")
        
        st.markdown("---")
        st.subheader("📋 Your Response Sheet & Answer Key")
        
        conn = get_db()
        st_res = pd.read_sql_query(
            "SELECT question_text, selected_option, correct_option, is_correct FROM student_responses WHERE quiz_id = ? AND LOWER(student_name) = ?",
            conn, params=(quiz_id, student_name.lower())
        )
        conn.close()
        
        if not st_res.empty:
            for idx, r_row in st_res.iterrows():
                is_right = (r_row['is_correct'] == 1)
                status_icon = "✅ Correct" if is_right else "❌ Incorrect"
                badge_color = "#28a745" if is_right else "#dc3545"
                
                st.markdown(f"""
                <div style="border-left: 5px solid {badge_color}; padding: 10px 14px; margin-bottom: 12px; background-color: #f8f9fa; border-radius: 6px;">
                    <b style="font-size: 15px;">Q{idx+1}. {r_row['question_text']}</b><br>
                    <span style="font-size: 14px;">Your Choice: <b>{r_row['selected_option']}</b> &nbsp; <span style="color: {badge_color}; font-weight: bold;">({status_icon})</span></span><br>
                    <span style="color: #1e7e34; font-size: 14px; font-weight: 600;">Correct Answer: {r_row['correct_option']}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Detailed responses are not available.")
            
        st.stop()

    questions_df = get_questions_by_quiz(quiz_id)
    if questions_df.empty:
        st.info("No questions have been added to this quiz yet.")
        st.stop()

    norm_name = student_name.lower()
    conn = get_db()
    attempt_row = conn.execute("SELECT start_epoch FROM quiz_attempts WHERE quiz_id = ? AND normalized_name = ?", (quiz_id, norm_name)).fetchone()
    conn.close()

    if not attempt_row:
        st.markdown("### 📌 Examination Guidelines & Proctoring Rules:")
        st.markdown(f"""
        - **Student Name:** `{student_name}` (SR: `{student_sr}`)
        - **Topic:** `{quiz_topic_val}`
        - **Duration:** `{quiz_dur_val} Minutes`
        - **Total Questions:** `{len(questions_df)}`
        - **Instructions:**
            1. Clicking **'Start Exam Now'** will initiate the continuous countdown timer (**{quiz_dur_val} minutes**).
            2. Refreshing, closing, or navigating away will NOT pause your timer.
            3. Tab switching is strictly monitored. On 3 violations, your test will automatically submit.
        """)
        if st.button("🚀 Start Exam Now", type="primary"):
            get_or_set_attempt_start(quiz_id, norm_name)
            st.rerun()
        st.stop()

    attempt_start = attempt_row["start_epoch"]
    elapsed = time.time() - attempt_start
    total_sec = quiz_dur_val * 60
    remaining = total_sec - elapsed

    if remaining <= 0:
        sub_time = get_ist_now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db()
        conn.execute('''
            INSERT OR REPLACE INTO submissions (quiz_id, student_name, sr_no, score, total_questions, tab_switches, status, submitted_at)
            VALUES (?, ?, ?, 0, ?, 0, 'Auto-Submitted (Time Up)', ?)
        ''', (quiz_id, student_name, student_sr, len(questions_df), sub_time))
        conn.commit()
        conn.close()
        st.error("⏰ Time Up! Your exam duration has ended and your test was auto-submitted.")
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
                
                is_correct = 1 if is_answer_correct(sel_opt, correct_opt, row['option_a'], row['option_b'], row['option_c'], row['option_d']) else 0
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
            st.success(f"🎉 Exam Successfully Submitted! Your Score: {score}/{len(questions_df)}")
            time.sleep(2)
            st.rerun()

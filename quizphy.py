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
# 1. PAGE CONFIGURATION, SEO & RESPONSIVE CSS
# ==========================================
st.set_page_config(
    page_title="Shashank Phy Quiz - ABIC Renukoot | Shashank Verma Physics Portal",
    page_icon="⚛️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Google Indexing & Crawler Meta Tags (SEO)
st.markdown("""
<head>
    <meta name="description" content="Official Physics Quiz and Academic Portal by Shashank Verma, TGT Physics at ABIC Renukoot. Class 11 and Class 12 Physics tests, student attendance, and results.">
    <meta name="keywords" content="shashank phy quiz, shashank physics quiz, shashank verma physics, abic renukoot physics, physics quiz shashank sir, abic quiz portal">
    <meta name="author" content="Shashank Verma">
    <meta name="robots" content="index, follow">
    <meta name="googlebot" content="index, follow, max-snippet:-1, max-image-preview:large">
</head>
<style>
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
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="school-header">
    <h1>ABIC RENUKOOT</h1>
    <h3>⚡ Physics Subject & Academic Portal ⚡</h3>
    <p>Mentor: <b>Shashank Verma, TGT (Physics)</b></p>
</div>
""", unsafe_allow_html=True)

DB_FILE = "master_quiz_system_prod_v17.db"
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

def clean_num(val):
    if pd.isna(val) or val is None or str(val).strip() == "":
        return 0
    try:
        return int(float(val))
    except Exception:
        return 0

def clean_sr_no(sr_val):
    if pd.isna(sr_val) or sr_val is None:
        return ""
    sr_str = str(sr_val).strip()
    if sr_str.endswith(".0"):
        sr_str = sr_str[:-2]
    return sr_str

def format_class_name(c_val):
    c_str = str(c_val).strip().lower()
    if "11" in c_str:
        return "Class 11"
    elif "12" in c_str:
        return "Class 12"
    return "Class 11"

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
    
    if s == c:
        return True
    
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
            normalized_name TEXT NOT NULL,
            roll_no INTEGER,
            target_class TEXT NOT NULL,
            UNIQUE(target_class, sr_no)
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
            is_active INTEGER DEFAULT 0
        )
    ''')

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

    c.execute('''
        CREATE TABLE IF NOT EXISTS student_profiles (
            sr_no TEXT PRIMARY KEY,
            roll_no INTEGER,
            class_sec TEXT,
            pen_number TEXT,
            dob TEXT,
            student_name TEXT,
            student_name_hindi TEXT,
            father_name TEXT,
            father_name_hindi TEXT,
            mother_name TEXT,
            category TEXT,
            mobile_no TEXT,
            email_id TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS student_test_marks (
            sr_no TEXT PRIMARY KEY,
            roll_no INTEGER,
            class_name TEXT DEFAULT 'Class 12',
            student_name TEXT,
            hindi REAL,
            english REAL,
            maths REAL,
            physics REAL,
            chemistry REAL,
            total_marks REAL
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS student_attendance (
            sr_no TEXT PRIMARY KEY,
            roll_no INTEGER,
            class_name TEXT DEFAULT 'Class 12',
            student_name TEXT,
            apr_days INTEGER,
            may_days INTEGER,
            july_days INTEGER,
            aug_days INTEGER,
            total_present INTEGER,
            percentage REAL
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS student_goals (
            sr_no TEXT PRIMARY KEY,
            roll_no INTEGER,
            class_name TEXT DEFAULT 'Class 12',
            student_name TEXT,
            short_term_goal TEXT,
            long_term_goal TEXT
        )
    ''')

    # Initial seeding only if no quizzes exist (never overrides user's toggle choices)
    c.execute("SELECT COUNT(*) FROM quizzes")
    if c.fetchone()[0] == 0:
        now_time = get_ist_now() - timedelta(hours=2)
        default_start = now_time.strftime("%Y-%m-%d %H:%M")
        default_end = (now_time + timedelta(days=60)).strftime("%Y-%m-%d %H:%M")
        c.execute('''
            INSERT INTO quizzes (target_class, topic, quiz_title, duration_minutes, start_datetime, end_datetime, is_active)
            VALUES ('Class 11', 'Laws of Motion & Work Energy', 'Class 11 - Physics Exam', 15, ?, ?, 1)
        ''', (default_start, default_end))
        c.execute('''
            INSERT INTO quizzes (target_class, topic, quiz_title, duration_minutes, start_datetime, end_datetime, is_active)
            VALUES ('Class 12', 'Electrostatics & Magnetism', 'Class 12 - Physics Exam', 20, ?, ?, 1)
        ''', (default_start, default_end))

    # Load students.xlsx (Class 11 & Class 12 automatic mapping)
    for s_file in ["students.xlsx", "students.csv"]:
        if os.path.exists(s_file):
            try:
                s_df = pd.read_csv(s_file) if s_file.endswith(".csv") else pd.read_excel(s_file)
                s_df.columns = [str(col).strip().lower().replace(" ", "_") for col in s_df.columns]
                cls_col = next((c for c in s_df.columns if "class" in c), None)
                nm_col = next((c for c in s_df.columns if "name" in c), s_df.columns[1] if len(s_df.columns) > 1 else s_df.columns[0])
                sr_col = next((c for c in s_df.columns if any(k in c for k in ["sr", "roll", "id", "password"])), s_df.columns[-1])
                
                for _, r in s_df.iterrows():
                    st_name = clean_text(r[nm_col])
                    st_sr = clean_sr_no(r[sr_col])
                    st_class = format_class_name(r[cls_col]) if cls_col else "Class 11"
                    if st_name and st_sr:
                        c.execute('''
                            INSERT OR REPLACE INTO master_students (student_name, sr_no, normalized_name, target_class)
                            VALUES (?, ?, ?, ?)
                        ''', (st_name, st_sr, st_name.lower(), st_class))
            except Exception:
                pass

    # Load XII B INFORMATION.xlsx
    if os.path.exists("XII B INFORMATION.xlsx"):
        try:
            df_info = pd.read_excel("XII B INFORMATION.xlsx", sheet_name="Sheet1 (5)")
            for _, r in df_info.iterrows():
                s_sr = clean_sr_no(r.get('S.R. NO.'))
                s_nm = clean_text(r.get("STUDENT'S NAME"))
                r_no = clean_num(r.get('ROLL NO.'))
                if s_sr and s_nm:
                    c.execute('''
                        INSERT OR REPLACE INTO master_students (student_name, sr_no, normalized_name, roll_no, target_class)
                        VALUES (?, ?, ?, ?, 'Class 12')
                    ''', (s_nm, s_sr, s_nm.lower(), r_no))

                    c.execute('''
                        INSERT OR REPLACE INTO student_profiles (sr_no, roll_no, class_sec, pen_number, dob, student_name, student_name_hindi, father_name, father_name_hindi, mother_name, category, mobile_no, email_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (s_sr, r_no, clean_text(r.get('class')), clean_text(r.get('PEN NUMBER')), str(r.get('D.O.B.', ''))[:10], s_nm, clean_text(r.get('STUDENT NAME IN HINDI')), clean_text(r.get("FATHER'S NAME")), clean_text(r.get("FATHER'S NAME IN HINDI")), clean_text(r.get("MOTHER'S NAME")), clean_text(r.get('CAT.')), clean_text(r.get('MOB. NO.')), clean_text(r.get('EMAIL ID'))))
        except Exception:
            pass

    c.execute("SELECT roll_no, sr_no FROM student_profiles WHERE roll_no IS NOT NULL")
    roll_to_sr = {row[0]: row[1] for row in c.fetchall()}

    if os.path.exists("attandance.xlsx"):
        try:
            df_att = pd.read_excel("attandance.xlsx")
            for _, r in df_att.iterrows():
                r_no = clean_num(r.get('S NO.'))
                s_sr = roll_to_sr.get(r_no, str(r_no))
                c.execute('''
                    INSERT OR REPLACE INTO student_attendance (sr_no, roll_no, class_name, student_name, apr_days, may_days, july_days, aug_days, total_present, percentage)
                    VALUES (?, ?, 'Class 12', ?, ?, ?, ?, ?, ?, ?)
                ''', (s_sr, r_no, clean_text(r.get('STUDENT NAME')), clean_num(r.iloc[2]), clean_num(r.get('MAY')), clean_num(r.get('july')), clean_num(r.get('AUG')), clean_num(r.get('TOAL FROM APR.2')), float(r.get('PER OUT OF 87 WORKING DAY', 0) or 0)))
        except Exception:
            pass

    if os.path.exists("MONTHLY TEST.xlsx"):
        try:
            df_mt = pd.read_excel("MONTHLY TEST.xlsx", sheet_name="Sheet1")
            for _, r in df_mt.iterrows():
                r_no = clean_num(r.get('ROLL NO'))
                s_sr = roll_to_sr.get(r_no, str(r_no))
                c.execute('''
                    INSERT OR REPLACE INTO student_test_marks (sr_no, roll_no, class_name, student_name, hindi, english, maths, physics, chemistry, total_marks)
                    VALUES (?, ?, 'Class 12', ?, ?, ?, ?, ?, ?, ?)
                ''', (s_sr, r_no, clean_text(r.get('STUDENT NAME')), clean_num(r.get('HINDI OUTOF 20')), clean_num(r.get('ENG OUTOF 20')), clean_num(r.get('MATHS OUTOF 20')), clean_num(r.get('PHY OUTOF 20')), clean_num(r.get('CHE OUTOF 20')), clean_num(r.get('TOTAL OUT OF 100'))))
        except Exception:
            pass

    if os.path.exists("studentresopnse.xlsx"):
        try:
            df_goals = pd.read_excel("studentresopnse.xlsx")
            for _, r in df_goals.iterrows():
                r_no = clean_num(r.get('Roll Number / अनुक्रमांक'))
                s_sr = roll_to_sr.get(r_no, str(r_no))
                c.execute('''
                    INSERT OR REPLACE INTO student_goals (sr_no, roll_no, class_name, student_name, short_term_goal, long_term_goal)
                    VALUES (?, ?, 'Class 12', ?, ?, ?)
                ''', (s_sr, r_no, clean_text(r.get("Student's Name / छात्र/छात्रा का नाम")), clean_text(r.get('अल्पकालिक लक्ष्य (Short-Term Goal - सत्र 2026-27)')), clean_text(r.get('दीर्घकालिक लक्ष्य (Long-Term Goal - उच्च शिक्षा एवं करियर)'))))
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

# Anti-Cheating & Live Timer Component
def inject_live_timer_and_security(remaining_seconds, quiz_id, student_name):
    timer_js = f"""
    <style>
        #sticky-timer-box {{
            position: fixed; 
            top: 45px; 
            right: 15px; 
            background: #d32f2f; 
            color: #ffffff; 
            padding: 8px 16px; 
            border-radius: 8px; 
            font-family: monospace; 
            font-size: 16px; 
            font-weight: bold; 
            z-index: 9999999;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            border: 2px solid #ffffff;
        }}
        @media only screen and (max-width: 600px) {{
            #sticky-timer-box {{
                top: 35px;
                right: 8px;
                padding: 6px 10px;
                font-size: 13px;
            }}
        }}
    </style>
    <div id="sticky-timer-box">
        ⏳ <span id="timer-display">Loading...</span> | ⚠️ Cheating: <span id="switch-count">0</span>/3
    </div>

    <script>
    let timeLeft = {int(remaining_seconds)};
    let display = document.getElementById('timer-display');
    let switchCountElem = document.getElementById('switch-count');
    let tabSwitches = parseInt(sessionStorage.getItem('tab_switches_{quiz_id}_{student_name}') || '0');
    switchCountElem.innerHTML = tabSwitches;

    function triggerAutoSubmit() {{
        let buttons = window.parent.document.querySelectorAll('button');
        buttons.forEach(btn => {{
            if (btn.innerText.includes("Submit Final Answers")) {{
                btn.click();
            }}
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

    function recordViolation() {{
        tabSwitches++;
        sessionStorage.setItem('tab_switches_{quiz_id}_{student_name}', tabSwitches);
        switchCountElem.innerHTML = tabSwitches;
        
        if (tabSwitches >= 3) {{
            alert('❌ MAXIMUM WARNINGS EXCEEDED!\\nAapne 3 baar tab switch kiya hai. Exam turant submit ho raha hai.');
            triggerAutoSubmit();
        }} else {{
            alert('⚠️ CHEATING WARNING (' + tabSwitches + '/3)!\\nTab switch ya doosra app kholna sakht mana hai.');
        }}
    }}

    window.addEventListener('blur', recordViolation);
    window.parent.document.addEventListener('contextmenu', function(e) {{ e.preventDefault(); }});
    window.parent.document.addEventListener('copy', function(e) {{ e.preventDefault(); }});
    window.parent.document.addEventListener('cut', function(e) {{ e.preventDefault(); }});
    window.parent.document.addEventListener('paste', function(e) {{ e.preventDefault(); }});
    </script>
    """
    components.html(timer_js, height=55)

# ==========================================
# 3. SIDEBAR NAVIGATION
# ==========================================
st.sidebar.title("🧭 Navigation")
selected_portal = st.sidebar.radio("Select Portal:", ["🎓 Student Portal (Exam & Records)", "⚙️ Admin Control Center"])
st.sidebar.divider()

# ==========================================
# 4. ADMIN CONTROL PANEL
# ==========================================
if selected_portal == "⚙️ Admin Control Center":
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False

    if not st.session_state.admin_authenticated:
        st.title("🔐 Admin Login Portal")
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
    quizzes_df = get_all_quizzes()
    admin_tab = st.selectbox("Select Management Section:", [
        "📚 Create & Manage Quizzes (Class & Topic Controls)",
        "📂 Academic Data Uploads (Class 11 / Class 12)",
        "👥 Master Student Directory (Excel/Manual)", 
        "📝 Question Bank (Excel/Manual)",
        "📊 Student Results & Controls"
    ])

    st.divider()

    # SECTION 1: QUIZZES (TOGGLE & START NOW FULLY WORKING)
    if admin_tab == "📚 Create & Manage Quizzes (Class & Topic Controls)":
        st.subheader("Quizzes & Instant Activation")
        with st.expander("➕ Create New Quiz", expanded=False):
            with st.form("new_quiz_form"):
                c_cls1, c_cls2 = st.columns(2)
                target_class_choice = c_cls1.selectbox("Select Target Class:", ["Class 11", "Class 12", "Class 9", "Class 10"])
                topic_name = c_cls2.text_input("Topic Name:", value="Motion in a Straight Line")
                q_title = st.text_input("Quiz Title:", value=f"{target_class_choice} - {topic_name}")
                q_dur = st.number_input("Duration (Minutes):", min_value=1, max_value=300, value=15)
                c_d1, c_d2 = st.columns(2)
                cur_ist = get_ist_now()
                start_date = c_d1.date_input("Start Date (IST):", value=cur_ist.date())
                start_time = c_d1.time_input("Start Time (IST):", value=(cur_ist - timedelta(minutes=10)).time())
                end_date = c_d2.date_input("End Date (IST):", value=(cur_ist + timedelta(days=60)).date())
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
                                VALUES (?, ?, ?, ?, ?, ?, 0)
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
                    top_val = r['topic'] if 'topic' in r and pd.notna(r['topic']) else 'General'
                    status_text = "🟢 ACTIVE (LIVE for Students)" if r['is_active'] == 1 else "🔴 DISABLED (Hidden)"
                    
                    st.markdown(f"🏷️ **Target Class:** `{cls_val}` | 📖 **Topic:** `{top_val}`")
                    st.markdown(f"⏱️ **Duration:** `{r['duration_minutes']} mins` | **Status:** **{status_text}**")
                    
                    col_b1, col_b2, col_b3 = st.columns([1.5, 1.5, 1])
                    
                    # TOGGLE BUTTON: Activates or Disables this specific quiz
                    toggle_btn_label = "🔴 Disable Quiz" if r['is_active'] == 1 else "🟢 Make Active (LIVE)"
                    if col_b1.button(toggle_btn_label, key=f"tog_{r['id']}"):
                        new_status = 0 if r['is_active'] == 1 else 1
                        conn = get_db()
                        # If turning ON, disable other quizzes of the SAME class so only 1 is live
                        if new_status == 1:
                            conn.execute("UPDATE quizzes SET is_active = 0 WHERE target_class = ?", (cls_val,))
                        conn.execute("UPDATE quizzes SET is_active = ? WHERE id = ?", (new_status, r['id']))
                        conn.commit()
                        conn.close()
                        st.rerun()
                    
                    # START NOW BUTTON: Instantly sets live window and activates
                    if col_b2.button(f"⚡ Start NOW (Instant Live)", key=f"now_{r['id']}"):
                        now_start = (get_ist_now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")
                        now_end = (get_ist_now() + timedelta(days=60)).strftime("%Y-%m-%d %H:%M")
                        conn = get_db()
                        conn.execute("UPDATE quizzes SET is_active = 0 WHERE target_class = ?", (cls_val,))
                        conn.execute("UPDATE quizzes SET start_datetime = ?, end_datetime = ?, is_active = 1 WHERE id = ?", (now_start, now_end, r['id']))
                        conn.commit()
                        conn.close()
                        st.success(f"{cls_val} ke liye yeh Quiz turant LIVE kar diya gaya hai!")
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
                    st.divider()

    # SECTION 2: ACADEMIC DATA UPLOADS
    elif admin_tab == "📂 Academic Data Uploads (Class 11 / Class 12)":
        st.subheader("📂 Academic Records & Student Excel Upload Center")
        
        target_upload_class = st.selectbox("Kaunsi Class ke liye upload karna hai?", ["Class 11", "Class 12"])

        up_choice = st.radio("Select File Type to Upload:", [
            "Students Master List (students.xlsx - Class, Name, SR No)",
            "Complete Student Info (Roll No, SR No, Details)",
            "Attendance Sheet", 
            "Monthly Test Marks",
            "Student Career Goals (Short & Long Term)"
        ], horizontal=True)

        up_file = st.file_uploader(f"Choose file for {target_upload_class} - {up_choice}:", type=["xlsx", "csv"])

        if up_file:
            conn = get_db()
            cur = conn.cursor()
            try:
                if up_choice == "Students Master List (students.xlsx - Class, Name, SR No)":
                    df = pd.read_csv(up_file) if up_file.name.endswith(".csv") else pd.read_excel(up_file)
                    df.columns = [str(col).strip().lower().replace(" ", "_") for col in df.columns]
                    cls_col = next((c for c in df.columns if "class" in c), None)
                    nm_col = next((c for c in df.columns if "name" in c), df.columns[1] if len(df.columns) > 1 else df.columns[0])
                    sr_col = next((c for c in df.columns if any(k in c for k in ["sr", "roll", "id", "password"])), df.columns[-1])
                    
                    cnt = 0
                    for _, r in df.iterrows():
                        st_name = clean_text(r[nm_col])
                        st_sr = clean_sr_no(r[sr_col])
                        st_class = format_class_name(r[cls_col]) if cls_col else target_upload_class
                        if st_name and st_sr:
                            cur.execute('''
                                INSERT OR REPLACE INTO master_students (student_name, sr_no, normalized_name, target_class)
                                VALUES (?, ?, ?, ?)
                            ''', (st_name, st_sr, st_name.lower(), st_class))
                            cnt += 1
                    conn.commit()
                    st.success(f"✅ {cnt} Students successfully imported/updated in master database!")

                elif up_choice == "Complete Student Info (Roll No, SR No, Details)":
                    xl = pd.ExcelFile(up_file)
                    sheet_name = 'Sheet1 (5)' if 'Sheet1 (5)' in xl.sheet_names else xl.sheet_names[0]
                    df = pd.read_excel(up_file, sheet_name=sheet_name)
                    df.columns = [str(c).strip() for c in df.columns]
                    
                    cnt = 0
                    for _, r in df.iterrows():
                        s_sr = clean_sr_no(r.get('S.R. NO.'))
                        s_nm = clean_text(r.get("STUDENT'S NAME"))
                        r_no = clean_num(r.get('ROLL NO.'))
                        if s_sr and s_nm:
                            cur.execute('''
                                INSERT OR REPLACE INTO master_students (student_name, sr_no, normalized_name, roll_no, target_class)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (s_nm, s_sr, s_nm.lower(), r_no, target_upload_class))
                            cur.execute('''
                                INSERT OR REPLACE INTO student_profiles (sr_no, roll_no, class_sec, pen_number, dob, student_name, student_name_hindi, father_name, father_name_hindi, mother_name, category, mobile_no, email_id)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (s_sr, r_no, target_upload_class, clean_text(r.get('PEN NUMBER')), str(r.get('D.O.B.', ''))[:10], s_nm, clean_text(r.get('STUDENT NAME IN HINDI')), clean_text(r.get("FATHER'S NAME")), clean_text(r.get("FATHER'S NAME IN HINDI")), clean_text(r.get("MOTHER'S NAME")), clean_text(r.get('CAT.')), clean_text(r.get('MOB. NO.')), clean_text(r.get('EMAIL ID'))))
                            cnt += 1
                    conn.commit()
                    st.success(f"✅ {cnt} Students Profiles registered for {target_upload_class}!")

                elif up_choice == "Attendance Sheet":
                    cur.execute("SELECT roll_no, sr_no FROM student_profiles WHERE roll_no IS NOT NULL")
                    roll_to_sr = {row[0]: row[1] for row in cur.fetchall()}
                    
                    df = pd.read_excel(up_file)
                    cnt = 0
                    for _, r in df.iterrows():
                        r_no = clean_num(r.get('S NO.'))
                        s_sr = roll_to_sr.get(r_no, str(r_no))
                        if r_no > 0:
                            cur.execute('''
                                INSERT OR REPLACE INTO student_attendance (sr_no, roll_no, class_name, student_name, apr_days, may_days, july_days, aug_days, total_present, percentage)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (s_sr, r_no, target_upload_class, clean_text(r.get('STUDENT NAME')), clean_num(r.iloc[2]), clean_num(r.get('MAY')), clean_num(r.get('july')), clean_num(r.get('AUG')), clean_num(r.get('TOAL FROM APR.2')), float(r.get('PER OUT OF 87 WORKING DAY', 0) or 0)))
                            cnt += 1
                    conn.commit()
                    st.success(f"✅ {cnt} Attendance records updated for {target_upload_class}!")

                elif up_choice == "Monthly Test Marks":
                    cur.execute("SELECT roll_no, sr_no FROM student_profiles WHERE roll_no IS NOT NULL")
                    roll_to_sr = {row[0]: row[1] for row in cur.fetchall()}

                    xl = pd.ExcelFile(up_file)
                    sheet = 'Sheet1' if 'Sheet1' in xl.sheet_names else xl.sheet_names[0]
                    df = pd.read_excel(up_file, sheet_name=sheet)
                    cnt = 0
                    for _, r in df.iterrows():
                        r_no = clean_num(r.get('ROLL NO'))
                        s_sr = roll_to_sr.get(r_no, str(r_no))
                        if r_no > 0:
                            cur.execute('''
                                INSERT OR REPLACE INTO student_test_marks (sr_no, roll_no, class_name, student_name, hindi, english, maths, physics, chemistry, total_marks)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (s_sr, r_no, target_upload_class, clean_text(r.get('STUDENT NAME')), clean_num(r.get('HINDI OUTOF 20')), clean_num(r.get('ENG OUTOF 20')), clean_num(r.get('MATHS OUTOF 20')), clean_num(r.get('PHY OUTOF 20')), clean_num(r.get('CHE OUTOF 20')), clean_num(r.get('TOTAL OUT OF 100'))))
                            cnt += 1
                    conn.commit()
                    st.success(f"✅ {cnt} Test marks saved for {target_upload_class}!")

                elif up_choice == "Student Career Goals (Short & Long Term)":
                    cur.execute("SELECT roll_no, sr_no FROM student_profiles WHERE roll_no IS NOT NULL")
                    roll_to_sr = {row[0]: row[1] for row in cur.fetchall()}

                    df = pd.read_excel(up_file)
                    cnt = 0
                    for _, r in df.iterrows():
                        r_no = clean_num(r.get('Roll Number / अनुक्रमांक'))
                        s_sr = roll_to_sr.get(r_no, str(r_no))
                        if r_no > 0:
                            cur.execute('''
                                INSERT OR REPLACE INTO student_goals (sr_no, roll_no, class_name, student_name, short_term_goal, long_term_goal)
                                VALUES (?, ?, ?, ?, ?, ?)
                            ''', (s_sr, r_no, target_upload_class, clean_text(r.get("Student's Name / छात्र/छात्रा का नाम")), clean_text(r.get('अल्पकालिक लक्ष्य (Short-Term Goal - सत्र 2026-27)')), clean_text(r.get('दीर्घकालिक लक्ष्य (Long-Term Goal - उच्च शिक्षा एवं करियर)'))))
                            cnt += 1
                    conn.commit()
                    st.success(f"✅ {cnt} Career Goals saved for {target_upload_class}!")
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                conn.close()

    # SECTION 3: DIRECTORY
    elif admin_tab == "👥 Master Student Directory (Excel/Manual)":
        st.subheader("👥 Registered Students Directory")
        conn = get_db()
        master_df = pd.read_sql_query("SELECT target_class AS 'Class', student_name AS 'Student Name', sr_no AS 'SR No (Password)', roll_no AS 'Roll No' FROM master_students ORDER BY target_class ASC, student_name ASC", conn)
        conn.close()
        if master_df.empty:
            st.info("No registered students found.")
        else:
            c11_cnt = len(master_df[master_df['Class'] == 'Class 11'])
            c12_cnt = len(master_df[master_df['Class'] == 'Class 12'])
            st.write(f"Total Enrolled: **{len(master_df)} Students** (Class 11: **{c11_cnt}**, Class 12: **{c12_cnt}**)")
            st.dataframe(master_df, use_container_width=True)

    # SECTION 4: QUESTION BANK
    elif admin_tab == "📝 Question Bank (Excel/Manual)":
        st.subheader("Question Bank Management")
        if quizzes_df.empty:
            st.info("Please create a quiz first.")
        else:
            quiz_options = {f"[{r.get('target_class','Class 11')}] {r['quiz_title']}": r['id'] for _, r in quizzes_df.iterrows()}
            sel_q_label = st.selectbox("Select Quiz:", list(quiz_options.keys()), key="q_quiz")
            sel_q_id = quiz_options[sel_q_label]
            
            with st.expander("📂 Bulk Upload Questions via Web", expanded=True):
                uploaded_q = st.file_uploader("Upload Questions File (.xlsx / .csv):", type=["xlsx", "csv"], key="q_file")
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
                st.divider()

    # SECTION 5: STUDENT RESULTS
    elif admin_tab == "📊 Student Results & Controls":
        st.subheader("Student Submissions & Merit Sheet")
        if quizzes_df.empty:
            st.info("No quizzes found.")
        else:
            quiz_options = {f"[{r.get('target_class','Class 11')}] {r['quiz_title']}": r['id'] for _, r in quizzes_df.iterrows()}
            sel_q_label = st.selectbox("Select Quiz to View Results:", list(quiz_options.keys()))
            sel_q_id = quiz_options[sel_q_label]
            
            conn = get_db()
            quiz_info_row = conn.execute("SELECT * FROM quizzes WHERE id = ?", (sel_q_id,)).fetchone()
            quiz_meta = dict(quiz_info_row) if quiz_info_row else {}
            
            subs_df = pd.read_sql_query(
                "SELECT student_name, sr_no, score, total_questions, tab_switches, status, submitted_at FROM submissions WHERE quiz_id = ? ORDER BY score DESC, submitted_at ASC", 
                conn, params=(sel_q_id,)
            )
            conn.close()
            
            if subs_df.empty:
                st.info("No submissions found for this quiz.")
            else:
                subs_df_display = subs_df.copy()
                subs_df_display.insert(0, "Rank", range(1, len(subs_df_display) + 1))
                st.write("### 🏆 Merit List")
                st.dataframe(subs_df_display, use_container_width=True)
                
                c_d1, c_d2 = st.columns(2)
                with c_d1:
                    pdf_bytes = generate_merit_pdf(subs_df, quiz_meta)
                    st.download_button("📄 Download Merit List (PDF)", data=pdf_bytes, file_name=f"Merit_List_{sel_q_id}.pdf", mime="application/pdf", type="primary")
                with c_d2:
                    csv_data = subs_df_display.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Download Results (CSV)", data=csv_data, file_name=f"results_{sel_q_id}.csv", mime="text/csv")

# ==========================================
# 5. STUDENT PORTAL (CLASS-LOCKED LOGIN)
# ==========================================
else:
    if "student_name" not in st.session_state:
        st.session_state.student_name = None
    if "student_sr" not in st.session_state:
        st.session_state.student_sr = None
    if "student_class" not in st.session_state:
        st.session_state.student_class = None

    # LOGIN FORM
    if not st.session_state.student_sr:
        st.subheader("🎓 Student Examination & Academic Portal")
        st.markdown("Pehle apni **Class** select karein aur apna **Password (SR Number)** darj karein.")
        
        col1, _ = st.columns([1.2, 1])
        with col1:
            with st.form("student_login_form"):
                sel_class = st.selectbox("Select Your Class:", ["Class 11", "Class 12"])
                in_sr = st.text_input("Password (Your SR Number):", type="password", placeholder="e.g. 38900")
                submit_login = st.form_submit_button("Sign In to Portal", type="primary")
                
                if submit_login:
                    clean_input_sr = clean_sr_no(in_sr)
                    
                    conn = get_db()
                    student_data = conn.execute(
                        "SELECT * FROM master_students WHERE sr_no = ? AND target_class = ?", 
                        (clean_input_sr, sel_class)
                    ).fetchone()
                    conn.close()
                    
                    if not clean_input_sr:
                        st.error("Kripya apna SR Number (Password) darj karein.")
                    elif not student_data:
                        st.error(f"❌ {sel_class} mein SR Number '{clean_input_sr}' registered nahi mila! Kripya sahi class aur SR number check karein.")
                    else:
                        st.session_state.student_name = student_data['student_name']
                        st.session_state.student_sr = clean_sr_no(student_data['sr_no'])
                        st.session_state.student_class = student_data['target_class']
                        st.success("Login successful!")
                        time.sleep(0.5)
                        st.rerun()
        st.stop()

    student_name = st.session_state.student_name
    student_sr = st.session_state.student_sr
    student_class = st.session_state.student_class

    st.sidebar.markdown(f"**🏷️ Class:** `{student_class}`")
    st.sidebar.markdown(f"**🔑 SR No:** `{student_sr}`")
    
    if st.sidebar.button("Log Out"):
        st.session_state.student_name = None
        st.session_state.student_sr = None
        st.session_state.student_class = None
        st.session_state.selected_quiz_id = None
        st.rerun()

    student_main_tab = st.radio("Navigation:", ["📝 Physics Live Examination", "📊 My Academic Dashboard & Goals"], horizontal=True)
    st.divider()

    # TAB 1: ACADEMIC DASHBOARD
    if student_main_tab == "📊 My Academic Dashboard & Goals":
        st.title(f"📊 Academic Progress & Profile — {student_class}")
        
        conn = get_db()
        prof = conn.execute("SELECT * FROM student_profiles WHERE sr_no = ?", (student_sr,)).fetchone()
        att = conn.execute("SELECT * FROM student_attendance WHERE sr_no = ?", (student_sr,)).fetchone()
        marks = conn.execute("SELECT * FROM student_test_marks WHERE sr_no = ?", (student_sr,)).fetchone()
        goals = conn.execute("SELECT * FROM student_goals WHERE sr_no = ?", (student_sr,)).fetchone()
        conn.close()

        tab_g, tab_m, tab_a, tab_p = st.tabs(["🎯 Goals & Aspirations", "📈 Monthly Test Marks", "📅 Attendance Report", "📋 Registered Profile"])

        with tab_g:
            st.subheader("🎯 Career & Academic Aspirations")
            if goals:
                st.markdown(f"""
                <div style="background:#e8f4fd; border-left: 6px solid #007bff; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                    <h4 style="margin:0 0 8px 0; color:#0056b3;">📌 अल्पकालिक लक्ष्य (Short-Term Goal — सत्र 2026-27):</h4>
                    <p style="font-size: 16px; margin:0; font-weight:500;">{goals['short_term_goal'] or 'Not Recorded'}</p>
                </div>
                <div style="background:#edf7ed; border-left: 6px solid #28a745; padding: 15px; border-radius: 8px;">
                    <h4 style="margin:0 0 8px 0; color:#1e7e34;">🚀 दीर्घकालिक लक्ष्य (Long-Term Goal — उच्च शिक्षा एवं करियर):</h4>
                    <p style="font-size: 16px; margin:0; font-weight:500;">{goals['long_term_goal'] or 'Not Recorded'}</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info(f"ℹ️ {student_class} ke liye career goals record abhi upload nahi huye hain.")

        with tab_m:
            st.subheader("📈 Monthly Test Marks")
            if marks:
                m1, m2, m3, m4, m5, m6 = st.columns(6)
                m1.metric("Hindi (20)", marks['hindi'])
                m2.metric("English (20)", marks['english'])
                m3.metric("Maths (20)", marks['maths'])
                m4.metric("Physics (20)", marks['physics'])
                m5.metric("Chemistry (20)", marks['chemistry'])
                m6.metric("Total Marks", f"{marks['total_marks']} / 100", f"{marks['total_marks']}%")
            else:
                st.info(f"ℹ️ {student_class} ke liye monthly test marks abhi upload nahi huye hain.")

        with tab_a:
            st.subheader("📅 Working Days Attendance Record")
            if att:
                a1, a2, a3, a4, a5 = st.columns(5)
                a1.metric("April", f"{att['apr_days']} Days")
                a2.metric("May", f"{att['may_days']} Days")
                a3.metric("July", f"{att['july_days']} Days")
                a4.metric("August", f"{att['aug_days']} Days")
                a5.metric("Total Present / %", f"{att['total_present']} Days", f"{att['percentage']:.1f}%")
                st.progress(min(1.0, max(0.0, float(att['percentage']) / 100.0)))
            else:
                st.info(f"ℹ️ {student_class} ke liye attendance record abhi upload nahi huye hain.")

        with tab_p:
            st.subheader("📋 Student School Information")
            if prof:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**Roll Number:** `{prof['roll_no']}`")
                    st.markdown(f"**Class & Section:** `{prof['class_sec']}`")
                    st.markdown(f"**Scholar Register (SR) No:** `{prof['sr_no']}`")
                    st.markdown(f"**Father's Name:** {prof['father_name']}")
                with c2:
                    st.markdown(f"**Mother's Name:** {prof['mother_name']}")
                    st.markdown(f"**Date of Birth:** `{prof['dob']}`")
                    st.markdown(f"**Category:** `{prof['category']}`")
                    st.markdown(f"**Registered Mobile:** `{prof['mobile_no']}`")
            else:
                st.info(f"ℹ️ {student_class} ke liye profile information abhi upload nahi huyi hai.")

    # TAB 2: LIVE EXAMINATION (ONLY SHOWS QUIZZES WHERE is_active == 1)
    elif student_main_tab == "📝 Physics Live Examination":
        quizzes_df = get_all_quizzes()
        
        s_cls_num = "11" if "11" in str(student_class) else "12"

        # STRICT FILTER: Sirf wahi quiz dikhega jo ACTIVE (is_active == 1) hai
        class_active_quizzes = quizzes_df[
            (quizzes_df['is_active'] == 1) & 
            (quizzes_df['target_class'].astype(str).str.contains(s_cls_num, case=False, na=False))
        ] if not quizzes_df.empty else pd.DataFrame()

        if class_active_quizzes.empty:
            st.warning(f"🛑 {student_class} ke liye abhi koi Physics Quiz Live nahi hai.")
            st.info("💡 **Notice:** Test shuru hone par yahan live paper automatically open ho jayega.")
            st.stop()

        if len(class_active_quizzes) == 1:
            quiz_id = class_active_quizzes.iloc[0]['id']
            quiz_title_val = class_active_quizzes.iloc[0]['quiz_title']
            quiz_topic_val = class_active_quizzes.iloc[0]['topic']
            quiz_dur_val = int(class_active_quizzes.iloc[0]['duration_minutes'])
        else:
            q_options = {f"{r['quiz_title']} ({r['topic']})": r['id'] for _, r in class_active_quizzes.iterrows()}
            sel_label = st.selectbox(f"Select {student_class} Live Exam:", list(q_options.keys()))
            quiz_id = q_options[sel_label]
            quiz_row = class_active_quizzes[class_active_quizzes['id'] == quiz_id].iloc[0]
            quiz_title_val = quiz_row['quiz_title']
            quiz_topic_val = quiz_row['topic']
            quiz_dur_val = int(quiz_row['duration_minutes'])

        conn = get_db()
        sub_check = conn.execute("SELECT * FROM submissions WHERE quiz_id = ? AND LOWER(student_name) = ?", (quiz_id, student_name.lower())).fetchone()
        conn.close()

        if sub_check:
            st.success(f"✅ Your exam for **'{quiz_title_val}'** has been successfully submitted!")
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
            st.markdown(f"### 📌 {quiz_title_val}")
            st.markdown(f"##### Target: **{student_class}** | Topic: **{quiz_topic_val}**")
            st.markdown(f"""
            - **Candidate SR No:** `{student_sr}`
            - **Exam Duration:** `{quiz_dur_val} Minutes`
            - **Total Questions:** `{len(questions_df)}`
            - **Anti-Cheating Rules:**
                1. 'Start Exam Now' par click karte hi timer chalu ho jayega.
                2. Screen par Google search ya tab switch karna mana hai. 3 warnings par exam auto-submit ho jayega.
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
            st.error("⏰ Time Up! Your exam was automatically submitted.")
            st.stop()

        inject_live_timer_and_security(remaining, quiz_id, student_name)

        # Examination Form
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

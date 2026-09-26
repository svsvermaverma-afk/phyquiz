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
    page_title="ABIC Renukoot - Physics Quiz & Academic Portal",
    page_icon="⚛️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
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
    .metric-card {
        background: #f8fafc;
        border-left: 5px solid #1e3c72;
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 12px;
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
    <h1>ABITYA BIRLA INTERMEDIATE COLLEGE, RENUKOOT</h1>
    <h3>⚡ Physics Subject & Academic Portal ⚡</h3>
    <p>Mentor: <b>Shashank Verma, TGT (Physics)</b></p>
</div>
""", unsafe_allow_html=True)

DB_FILE = "master_quiz_system_prod_v18.db"
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

# ==========================================
# 2. DATABASE INITIALIZATION & SCHEMA
# ==========================================
def get_db():
    conn = sqlite3.connect(DB_FILE, timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # 1. Master Students Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS master_students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll_no INTEGER UNIQUE,
            student_name TEXT NOT NULL,
            sr_no TEXT NOT NULL,
            normalized_name TEXT NOT NULL
        )
    ''')
    
    # 2. Complete Profile Table (From XII B INFORMATION)
    c.execute('''
        CREATE TABLE IF NOT EXISTS student_profiles (
            roll_no INTEGER PRIMARY KEY,
            class_sec TEXT,
            sr_no TEXT,
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

    # 3. Monthly Test Marks Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS student_test_marks (
            roll_no INTEGER PRIMARY KEY,
            student_name TEXT,
            hindi REAL,
            english REAL,
            maths REAL,
            physics REAL,
            chemistry REAL,
            total_marks REAL
        )
    ''')

    # 4. Attendance Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS student_attendance (
            roll_no INTEGER PRIMARY KEY,
            student_name TEXT,
            apr_days INTEGER,
            may_days INTEGER,
            july_days INTEGER,
            aug_days INTEGER,
            total_present INTEGER,
            percentage REAL
        )
    ''')

    # 5. Career & Academic Goals Table (Short & Long Term)
    c.execute('''
        CREATE TABLE IF NOT EXISTS student_goals (
            roll_no INTEGER PRIMARY KEY,
            student_name TEXT,
            short_term_goal TEXT,
            long_term_goal TEXT
        )
    ''')

    # 6. Existing Quiz Tables
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
    
    # Default Demo Quiz Setup
    now_time = get_ist_now() - timedelta(hours=1)
    default_start = now_time.strftime("%Y-%m-%d %H:%M")
    default_end = (now_time + timedelta(days=30)).strftime("%Y-%m-%d %H:%M")
    
    c.execute('''
        INSERT OR IGNORE INTO quizzes (target_class, topic, quiz_title, duration_minutes, start_datetime, end_datetime, is_active)
        VALUES (?, ?, ?, ?, ?, ?, 1)
    ''', ("Class 12", "Electrostatics & Magnetism", "Class 12 - Physics Exam", 20, default_start, default_end))

    # Auto-load files if placed locally in repository
    if os.path.exists("XII B INFORMATION.xlsx"):
        try:
            df_info = pd.read_excel("XII B INFORMATION.xlsx", sheet_name="Sheet1 (5)")
            for _, r in df_info.iterrows():
                r_no = clean_num(r.get('ROLL NO.'))
                if r_no > 0:
                    s_nm = clean_text(r.get("STUDENT'S NAME"))
                    s_sr = clean_sr_no(r.get('S.R. NO.'))
                    c.execute('''
                        INSERT OR REPLACE INTO master_students (roll_no, student_name, sr_no, normalized_name)
                        VALUES (?, ?, ?, ?)
                    ''', (r_no, s_nm, s_sr, s_nm.lower()))
                    c.execute('''
                        INSERT OR REPLACE INTO student_profiles (roll_no, class_sec, sr_no, pen_number, dob, student_name, student_name_hindi, father_name, father_name_hindi, mother_name, category, mobile_no, email_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (r_no, clean_text(r.get('class')), s_sr, clean_text(r.get('PEN NUMBER')), str(r.get('D.O.B.', ''))[:10], s_nm, clean_text(r.get('STUDENT NAME IN HINDI')), clean_text(r.get("FATHER'S NAME")), clean_text(r.get("FATHER'S NAME IN HINDI")), clean_text(r.get("MOTHER'S NAME")), clean_text(r.get('CAT.')), clean_text(r.get('MOB. NO.')), clean_text(r.get('EMAIL ID'))))
        except Exception:
            pass

    if os.path.exists("attandance.xlsx"):
        try:
            df_att = pd.read_excel("attandance.xlsx")
            for _, r in df_att.iterrows():
                r_no = clean_num(r.get('S NO.'))
                if r_no > 0:
                    c.execute('''
                        INSERT OR REPLACE INTO student_attendance (roll_no, student_name, apr_days, may_days, july_days, aug_days, total_present, percentage)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (r_no, clean_text(r.get('STUDENT NAME')), clean_num(r.iloc[2]), clean_num(r.get('MAY')), clean_num(r.get('july')), clean_num(r.get('AUG')), clean_num(r.get('TOAL FROM APR.2')), float(r.get('PER OUT OF 87 WORKING DAY', 0) or 0)))
        except Exception:
            pass

    if os.path.exists("MONTHLY TEST.xlsx"):
        try:
            df_mt = pd.read_excel("MONTHLY TEST.xlsx", sheet_name="Sheet1")
            for _, r in df_mt.iterrows():
                r_no = clean_num(r.get('ROLL NO'))
                if r_no > 0:
                    c.execute('''
                        INSERT OR REPLACE INTO student_test_marks (roll_no, student_name, hindi, english, maths, physics, chemistry, total_marks)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (r_no, clean_text(r.get('STUDENT NAME')), clean_num(r.get('HINDI OUTOF 20')), clean_num(r.get('ENG OUTOF 20')), clean_num(r.get('MATHS OUTOF 20')), clean_num(r.get('PHY OUTOF 20')), clean_num(r.get('CHE OUTOF 20')), clean_num(r.get('TOTAL OUT OF 100'))))
        except Exception:
            pass

    if os.path.exists("studentresopnse.xlsx"):
        try:
            df_goals = pd.read_excel("studentresopnse.xlsx")
            for _, r in df_goals.iterrows():
                r_no = clean_num(r.get('Roll Number / अनुक्रमांक'))
                if r_no > 0:
                    c.execute('''
                        INSERT OR REPLACE INTO student_goals (roll_no, student_name, short_term_goal, long_term_goal)
                        VALUES (?, ?, ?, ?)
                    ''', (r_no, clean_text(r.get("Student's Name / छात्र/छात्रा का नाम")), clean_text(r.get('अल्पकालिक लक्ष्य (Short-Term Goal - सत्र 2026-27)')), clean_text(r.get('दीर्घकालिक लक्ष्य (Long-Term Goal - उच्च शिक्षा एवं करियर)'))))
        except Exception:
            pass

    conn.commit()
    conn.close()

init_db()

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================
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
    mapping = {'a': a, 'option a': a, '(a)': a, '1': a, 'b': b, 'option b': b, '(b)': b, '2': b, 'c': c_opt, 'option c': c_opt, '(c)': c_opt, '3': c_opt, 'd': d, 'option d': d, '(d)': d, '4': d}
    if c in mapping and s == mapping[c]:
        return True
    return False

# ==========================================
# 4. SIDEBAR & NAVIGATION
# ==========================================
st.sidebar.title("🧭 Navigation")
selected_portal = st.sidebar.radio("Select Portal:", [
    "🎓 Student Exam Portal", 
    "📊 My Academic Dashboard (Profile & Goals)", 
    "⚙️ Admin Control Center"
])
st.sidebar.divider()

# ==========================================
# 5. STUDENT ACADEMIC DASHBOARD (ROLL NO MATCH)
# ==========================================
if selected_portal == "📊 My Academic Dashboard (Profile & Goals)":
    st.title("📊 Student Academic Dashboard & Progress Report")
    st.markdown("Enter your **Roll Number** to view your attendance, monthly test marks, profile details, and registered goals.")
    
    col_input, _ = st.columns([1, 1.5])
    with col_input:
        search_roll = st.number_input("Enter Roll Number:", min_value=1, max_value=200, step=1, value=1)
        btn_view = st.button("🔍 View Academic Record", type="primary")

    if btn_view or search_roll:
        conn = get_db()
        prof = conn.execute("SELECT * FROM student_profiles WHERE roll_no = ?", (search_roll,)).fetchone()
        att = conn.execute("SELECT * FROM student_attendance WHERE roll_no = ?", (search_roll,)).fetchone()
        marks = conn.execute("SELECT * FROM student_test_marks WHERE roll_no = ?", (search_roll,)).fetchone()
        goals = conn.execute("SELECT * FROM student_goals WHERE roll_no = ?", (search_roll,)).fetchone()
        conn.close()

        if not prof and not att and not marks and not goals:
            st.warning(f"No records found for Roll Number: {search_roll}. Please verify or contact your teacher.")
        else:
            student_display_name = prof['student_name'] if prof else (att['student_name'] if att else "Student")
            hindi_name = f"({prof['student_name_hindi']})" if prof and prof['student_name_hindi'] else ""
            
            st.success(f"### 👤 {student_display_name} {hindi_name} — Roll No: {search_roll}")
            
            tab1, tab2, tab3, tab4 = st.tabs(["🎯 Goals & Vision", "📈 Monthly Test Report", "📅 Attendance", "📋 Student Profile"])
            
            # TAB 1: SHORT & LONG TERM GOALS
            with tab1:
                st.subheader("🎯 Academic & Career Aspirations")
                if goals:
                    st.markdown(f"""
                    <div style="background:#e8f4fd; border-left: 6px solid #007bff; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                        <h4 style="margin:0 0 8px 0; color:#0056b3;">📌 अल्पकालिक लक्ष्य (Short-Term Goal — 2026-27):</h4>
                        <p style="font-size: 16px; margin:0; font-weight:500;">{goals['short_term_goal'] or 'Not Specified'}</p>
                    </div>
                    <div style="background:#edf7ed; border-left: 6px solid #28a745; padding: 15px; border-radius: 8px;">
                        <h4 style="margin:0 0 8px 0; color:#1e7e34;">🚀 दीर्घकालिक लक्ष्य (Long-Term Goal — Higher Education & Career):</h4>
                        <p style="font-size: 16px; margin:0; font-weight:500;">{goals['long_term_goal'] or 'Not Specified'}</p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.info("Goals have not been recorded yet for this student.")

            # TAB 2: MONTHLY TEST
            with tab2:
                st.subheader("📝 Monthly Test Performance")
                if marks:
                    m1, m2, m3, m4, m5, m6 = st.columns(6)
                    m1.metric("Hindi (20)", marks['hindi'])
                    m2.metric("English (20)", marks['english'])
                    m3.metric("Maths (20)", marks['maths'])
                    m4.metric("Physics (20)", marks['physics'])
                    m5.metric("Chemistry (20)", marks['chemistry'])
                    m6.metric("Total (100)", f"{marks['total_marks']}", delta=f"{marks['total_marks']}%")
                else:
                    st.info("Monthly test records are not available for this roll number.")

            # TAB 3: ATTENDANCE
            with tab3:
                st.subheader("📅 Attendance Record")
                if att:
                    a1, a2, a3, a4, a5 = st.columns(5)
                    a1.metric("April", f"{att['apr_days']} Days")
                    a2.metric("May", f"{att['may_days']} Days")
                    a3.metric("July", f"{att['july_days']} Days")
                    a4.metric("August", f"{att['aug_days']} Days")
                    a5.metric("Total Present / %", f"{att['total_present']} Days", f"{att['percentage']:.1f}%")
                    
                    st.progress(min(1.0, max(0.0, float(att['percentage']) / 100.0)))
                else:
                    st.info("Attendance records are not available for this roll number.")

            # TAB 4: PROFILE
            with tab4:
                st.subheader("📋 Registered School Information")
                if prof:
                    p1, p2 = st.columns(2)
                    with p1:
                        st.markdown(f"**Class & Section:** `{prof['class_sec']}`")
                        st.markdown(f"**Scholar Register (SR) No:** `{prof['sr_no']}`")
                        st.markdown(f"**Father's Name:** `{prof['father_name']}` ({prof['father_name_hindi']})")
                        st.markdown(f"**Mother's Name:** `{prof['mother_name']}`")
                    with p2:
                        st.markdown(f"**Date of Birth:** `{prof['dob']}`")
                        st.markdown(f"**Category:** `{prof['category']}`")
                        st.markdown(f"**Registered Mobile:** `{prof['mobile_no']}`")
                        st.markdown(f"**Registered Email:** `{prof['email_id']}`")
                else:
                    st.info("Profile information is not available.")

# ==========================================
# 6. ADMIN CONTROL CENTER (EXCEL UPLOADS)
# ==========================================
elif selected_portal == "⚙️ Admin Control Center":
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False

    if not st.session_state.admin_authenticated:
        st.title("🔐 Admin Login Portal")
        col1, _ = st.columns([1.2, 1])
        with col1:
            with st.form("admin_login_form"):
                in_user = st.text_input("Admin Username:")
                in_pass = st.text_input("Admin Password:", type="password")
                if st.form_submit_button("Sign In as Admin", type="primary"):
                    if in_user.strip() == ADMIN_USERNAME and in_pass.strip() == ADMIN_PASSWORD:
                        st.session_state.admin_authenticated = True
                        st.success("Admin login successful!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Invalid Credentials!")
        st.stop()

    st.sidebar.success(f"👑 Logged in as: `{ADMIN_USERNAME}`")
    if st.sidebar.button("Log Out Admin"):
        st.session_state.admin_authenticated = False
        st.rerun()

    st.title("⚙️ Teacher & Examination Control Center")
    admin_tab = st.selectbox("Select Management Section:", [
        "📂 Academic Data Uploads (Attendance / Tests / Goals / Info)",
        "📚 Create & Manage Quizzes", 
        "📝 Question Bank Management",
        "📊 Student Results & Merit List", 
        "👥 Master Student Directory"
    ])

    # ACADEMIC DATA UPLOAD SECTION
    if admin_tab == "📂 Academic Data Uploads (Attendance / Tests / Goals / Info)":
        st.subheader("📂 Upload Permanent Academic Records")
        st.markdown("Yahan se aap Attendance, Monthly Test Marks, Student Info, aur Goals ki files direct upload kar sakte hain:")

        up_choice = st.radio("Select File Type to Upload:", [
            "Attendance Sheet (attandance.xlsx)", 
            "Monthly Test Marks (MONTHLY TEST.xlsx)",
            "Student Career Goals (studentresopnse.xlsx)",
            "Complete Student Info (XII B INFORMATION.xlsx)"
        ], horizontal=True)

        up_file = st.file_uploader(f"Choose file for {up_choice}:", type=["xlsx", "csv"])

        if up_file:
            conn = get_db()
            cur = conn.cursor()
            try:
                if up_choice == "Attendance Sheet (attandance.xlsx)":
                    df = pd.read_excel(up_file)
                    cnt = 0
                    for _, r in df.iterrows():
                        r_no = clean_num(r.get('S NO.'))
                        if r_no > 0:
                            cur.execute('''
                                INSERT OR REPLACE INTO student_attendance (roll_no, student_name, apr_days, may_days, july_days, aug_days, total_present, percentage)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (r_no, clean_text(r.get('STUDENT NAME')), clean_num(r.iloc[2]), clean_num(r.get('MAY')), clean_num(r.get('july')), clean_num(r.get('AUG')), clean_num(r.get('TOAL FROM APR.2')), float(r.get('PER OUT OF 87 WORKING DAY', 0) or 0)))
                            cnt += 1
                    conn.commit()
                    st.success(f"✅ {cnt} Attendance records updated successfully!")

                elif up_choice == "Monthly Test Marks (MONTHLY TEST.xlsx)":
                    xl = pd.ExcelFile(up_file)
                    sheet = 'Sheet1' if 'Sheet1' in xl.sheet_names else xl.sheet_names[0]
                    df = pd.read_excel(up_file, sheet_name=sheet)
                    cnt = 0
                    for _, r in df.iterrows():
                        r_no = clean_num(r.get('ROLL NO'))
                        if r_no > 0:
                            cur.execute('''
                                INSERT OR REPLACE INTO student_test_marks (roll_no, student_name, hindi, english, maths, physics, chemistry, total_marks)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (r_no, clean_text(r.get('STUDENT NAME')), clean_num(r.get('HINDI OUTOF 20')), clean_num(r.get('ENG OUTOF 20')), clean_num(r.get('MATHS OUTOF 20')), clean_num(r.get('PHY OUTOF 20')), clean_num(r.get('CHE OUTOF 20')), clean_num(r.get('TOTAL OUT OF 100'))))
                            cnt += 1
                    conn.commit()
                    st.success(f"✅ {cnt} Student Test marks saved successfully!")

                elif up_choice == "Student Career Goals (studentresopnse.xlsx)":
                    df = pd.read_excel(up_file)
                    cnt = 0
                    for _, r in df.iterrows():
                        r_no = clean_num(r.get('Roll Number / अनुक्रमांक'))
                        if r_no > 0:
                            cur.execute('''
                                INSERT OR REPLACE INTO student_goals (roll_no, student_name, short_term_goal, long_term_goal)
                                VALUES (?, ?, ?, ?)
                            ''', (r_no, clean_text(r.get("Student's Name / छात्र/छात्रा का नाम")), clean_text(r.get('अल्पकालिक लक्ष्य (Short-Term Goal - सत्र 2026-27)')), clean_text(r.get('दीर्घकालिक लक्ष्य (Long-Term Goal - उच्च शिक्षा एवं करियर)'))))
                            cnt += 1
                    conn.commit()
                    st.success(f"✅ {cnt} Student Goals updated successfully!")

                elif up_choice == "Complete Student Info (XII B INFORMATION.xlsx)":
                    xl = pd.ExcelFile(up_file)
                    sheet = 'Sheet1 (5)' if 'Sheet1 (5)' in xl.sheet_names else xl.sheet_names[0]
                    df = pd.read_excel(up_file, sheet_name=sheet)
                    cnt = 0
                    for _, r in df.iterrows():
                        r_no = clean_num(r.get('ROLL NO.'))
                        if r_no > 0:
                            s_nm = clean_text(r.get("STUDENT'S NAME"))
                            s_sr = clean_sr_no(r.get('S.R. NO.'))
                            cur.execute('''
                                INSERT OR REPLACE INTO master_students (roll_no, student_name, sr_no, normalized_name)
                                VALUES (?, ?, ?, ?)
                            ''', (r_no, s_nm, s_sr, s_nm.lower()))
                            cur.execute('''
                                INSERT OR REPLACE INTO student_profiles (roll_no, class_sec, sr_no, pen_number, dob, student_name, student_name_hindi, father_name, father_name_hindi, mother_name, category, mobile_no, email_id)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (r_no, clean_text(r.get('class')), s_sr, clean_text(r.get('PEN NUMBER')), str(r.get('D.O.B.', ''))[:10], s_nm, clean_text(r.get('STUDENT NAME IN HINDI')), clean_text(r.get("FATHER'S NAME")), clean_text(r.get("FATHER'S NAME IN HINDI")), clean_text(r.get("MOTHER'S NAME")), clean_text(r.get('CAT.')), clean_text(r.get('MOB. NO.')), clean_text(r.get('EMAIL ID'))))
                            cnt += 1
                    conn.commit()
                    st.success(f"✅ {cnt} Student Profiles registered successfully!")
            except Exception as e:
                st.error(f"Error parsing file: {e}")
            finally:
                conn.close()

    # SECTION: OTHER ADMIN MENUS (QUIZ CREATION, ETC.)
    elif admin_tab == "📚 Create & Manage Quizzes":
        st.subheader("Quiz Controls")
        quizzes_df = get_all_quizzes()
        st.dataframe(quizzes_df, use_container_width=True)

# ==========================================
# 7. STUDENT EXAM PORTAL
# ==========================================
else:
    st.subheader("🎓 Student Online Exam Portal")
    quizzes_df = get_all_quizzes()
    active_quizzes = quizzes_df[quizzes_df['is_active'] == 1] if not quizzes_df.empty else pd.DataFrame()

    if active_quizzes.empty:
        st.error("🛑 No exams are currently active.")
        st.stop()

    if "student_name" not in st.session_state or not st.session_state.student_name:
        col1, _ = st.columns([1.2, 1])
        with col1:
            with st.form("exam_login"):
                in_roll = st.number_input("Enter Roll Number:", min_value=1, max_value=200, step=1, value=1)
                in_sr = st.text_input("Password (Your SR Number):", type="password")
                if st.form_submit_button("Enter Quiz", type="primary"):
                    conn = get_db()
                    stu = conn.execute("SELECT * FROM master_students WHERE roll_no = ?", (in_roll,)).fetchone()
                    conn.close()
                    if not stu:
                        st.error(f"Roll Number {in_roll} not registered!")
                    elif clean_sr_no(stu['sr_no']) != clean_sr_no(in_sr):
                        st.error("Incorrect Password (SR Number mismatch)!")
                    else:
                        st.session_state.student_name = stu['student_name']
                        st.session_state.student_sr = clean_sr_no(stu['sr_no'])
                        st.session_state.selected_quiz_id = active_quizzes.iloc[0]['id']
                        st.success(f"Welcome {stu['student_name']}!")
                        st.rerun()

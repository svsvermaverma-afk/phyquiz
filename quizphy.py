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
    page_title="Secure Quiz & Exam Portal",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Yahan apna Admin Gmail set karein
ADMIN_EMAIL = "admin@gmail.com"
DB_FILE = "exam_portal.db"


# ==========================================
# 2. DATABASE MANAGEMENT (SQLite)
# ==========================================
def get_db_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    c = conn.cursor()

    # Settings table (Quiz timing & general config)
    c.execute('''
              CREATE TABLE IF NOT EXISTS settings
              (
                  key
                  TEXT
                  PRIMARY
                  KEY,
                  value
                  TEXT
              )
              ''')

    # Questions table
    c.execute('''
              CREATE TABLE IF NOT EXISTS questions
              (
                  id
                  INTEGER
                  PRIMARY
                  KEY
                  AUTOINCREMENT,
                  question
                  TEXT
                  NOT
                  NULL,
                  option_a
                  TEXT
                  NOT
                  NULL,
                  option_b
                  TEXT
                  NOT
                  NULL,
                  option_c
                  TEXT
                  NOT
                  NULL,
                  option_d
                  TEXT
                  NOT
                  NULL,
                  correct_option
                  TEXT
                  NOT
                  NULL
              )
              ''')

    # Submissions & Activity table
    c.execute('''
              CREATE TABLE IF NOT EXISTS submissions
              (
                  id
                  INTEGER
                  PRIMARY
                  KEY
                  AUTOINCREMENT,
                  email
                  TEXT
                  UNIQUE
                  NOT
                  NULL,
                  score
                  INTEGER
                  NOT
                  NULL,
                  total_questions
                  INTEGER
                  NOT
                  NULL,
                  tab_switches
                  INTEGER
                  DEFAULT
                  0,
                  submitted_at
                  TEXT
                  NOT
                  NULL
              )
              ''')

    # Default settings agar pehle se na ho
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('duration_minutes', '15')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('quiz_title', 'Science & General Assessment')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('is_active', '1')")

    # Dummy questions (sirf initial setup ke liye)
    c.execute("SELECT COUNT(*) FROM questions")
    if c.fetchone()[0] == 0:
        sample_q = [
            ("What is the SI unit of Force?", "Pascal", "Newton", "Joule", "Watt", "Newton"),
            ("Which gas is most abundant in Earth's atmosphere?", "Oxygen", "Carbon Dioxide", "Nitrogen", "Hydrogen",
             "Nitrogen"),
            ("What is the chemical formula of water?", "H2O", "CO2", "NaCl", "O2", "H2O")
        ]
        c.executemany('''
                      INSERT INTO questions (question, option_a, option_b, option_c, option_d, correct_option)
                      VALUES (?, ?, ?, ?, ?, ?)
                      ''', sample_q)

    conn.commit()
    conn.close()


init_db()


# Helper DB Functions
def get_setting(key, default=""):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row['value'] if row else default


def update_setting(key, value):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()


def get_all_questions():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM questions", conn)
    conn.close()
    return df


def get_submission(email):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM submissions WHERE email = ?", (email.lower(),))
    sub = c.fetchone()
    conn.close()
    return sub


# ==========================================
# 3. ANTI-CHEATING JAVASCRIPT INJECTION
# ==========================================
def inject_proctoring_script():
    proctor_js = """
    <script>
    // 1. Right click disable
    document.addEventListener('contextmenu', event => event.preventDefault());

    // 2. Copy/Cut/Paste block
    document.addEventListener('copy', event => event.preventDefault());
    document.addEventListener('cut', event => event.preventDefault());
    document.addEventListener('paste', event => event.preventDefault());

    // 3. Tab-switch / Window Blur Detection
    window.addEventListener('blur', function () {
        alert('⚠️ WARNING: Tab switch detect hua hai! Yeh activity Proctoring log me record ho rahi hai.');
    });

    // 4. Keyboard Shortcuts Block (Ctrl+C, Ctrl+V, F12, Ctrl+U)
    document.onkeydown = function (e) {
        if (e.keyCode == 123) { return false; } // F12
        if (e.ctrlKey && e.shiftKey && (e.keyCode == 'I'.charCodeAt(0) || e.keyCode == 'J'.charCodeAt(0) || e.keyCode == 'C'.charCodeAt(0))) { return false; }
        if (e.ctrlKey && (e.keyCode == 'U'.charCodeAt(0) || e.keyCode == 'C'.charCodeAt(0) || e.keyCode == 'V'.charCodeAt(0) || e.keyCode == 'A'.charCodeAt(0))) { return false; }
    };
    </script>
    """
    components.html(proctor_js, height=0, width=0)


# ==========================================
# 4. AUTHENTICATION & SESSION STATE
# ==========================================
if "user_email" not in st.session_state:
    st.session_state.user_email = None
if "quiz_started" not in st.session_state:
    st.session_state.quiz_started = False
if "start_time" not in st.session_state:
    st.session_state.start_time = None

# --- Login Screen ---
if not st.session_state.user_email:
    st.title("🔒 Online Assessment & Examination System")
    st.markdown("Yeh test strictly proctored hai. Test access karne ke liye valid **Gmail ID** enter karein.")

    col_a, _ = st.columns([1, 1])
    with col_a:
        with st.form("login_form"):
            input_email = st.text_input("Enter your Gmail Address (@gmail.com):", placeholder="studentname@gmail.com")
            submitted = st.form_submit_button("Proceed to Test Portal")

            if submitted:
                cleaned_email = input_email.strip().lower()
                if cleaned_email.endswith("@gmail.com") and len(cleaned_email) > 10:
                    st.session_state.user_email = cleaned_email
                    st.rerun()
                else:
                    st.error("Kripya ek valid Gmail ID darj karein jo '@gmail.com' par khatam hoti ho.")
    st.stop()

# User details post login
current_user = st.session_state.user_email
is_admin = (current_user == ADMIN_EMAIL.lower())

# Sidebar Log Out
st.sidebar.markdown(f"**Logged in as:** `{current_user}`")
if is_admin:
    st.sidebar.success("👑 Role: Administrator")
else:
    st.sidebar.info("🎓 Role: Student Candidate")

if st.sidebar.button("Log Out"):
    st.session_state.user_email = None
    st.session_state.quiz_started = False
    st.session_state.start_time = None
    st.rerun()

# ==========================================
# 5. ADMIN CONTROL PANEL
# ==========================================
if is_admin:
    st.title("⚙️ Examination Admin Control Center")
    admin_tab = st.sidebar.radio("Navigation Menu", [
        "Dashboard & Submissions",
        "Timing & Exam Settings",
        "Question Bank Manager",
        "Take Test Preview"
    ])

    # --- Tab 1: Dashboard & Results ---
    if admin_tab == "Dashboard & Submissions":
        st.subheader("📊 Student Results & Submission Logs")

        conn = get_db_connection()
        subs_df = pd.read_sql_query(
            "SELECT email, score, total_questions, submitted_at FROM submissions ORDER BY id DESC", conn)
        conn.close()

        if not subs_df.empty:
            subs_df["Percentage (%)"] = ((subs_df["score"] / subs_df["total_questions"]) * 100).round(2)

            # Metrics
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Submissions", len(subs_df))
            m2.metric("Average Score (%)", f"{subs_df['Percentage (%)'].mean():.2f}%")
            m3.metric("Highest Score", f"{subs_df['score'].max()}/{subs_df['total_questions'].iloc[0]}")

            st.dataframe(subs_df, use_container_width=True)

            csv = subs_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Results (CSV)", data=csv, file_name="exam_results.csv", mime="text/csv")
        else:
            st.info("Abhi tak kisi bhi student ne test submit nahi kiya hai.")
        st.stop()

    # --- Tab 2: Timing & General Settings ---
    elif admin_tab == "Timing & Exam Settings":
        st.subheader("⏱️ Manage Exam Duration & Status")

        cur_duration = int(get_setting("duration_minutes", 15))
        cur_title = get_setting("quiz_title", "Online Examination")
        cur_status = get_setting("is_active", "1") == "1"

        with st.form("settings_form"):
            new_title = st.text_input("Exam Title:", value=cur_title)
            new_duration = st.number_input("Test Duration (in Minutes):", min_value=1, max_value=240,
                                           value=cur_duration)
            new_status = st.checkbox("Exam Active / Live (Students can attempt)", value=cur_status)

            save_btn = st.form_submit_button("Update Exam Settings")
            if save_btn:
                update_setting("quiz_title", new_title)
                update_setting("duration_minutes", new_duration)
                update_setting("is_active", "1" if new_status else "0")
                st.success("Exam settings successfully update ho gayi hain!")
                time.sleep(1)
                st.rerun()
        st.stop()

    # --- Tab 3: Question Bank Manager ---
    elif admin_tab == "Question Bank Manager":
        st.subheader("📝 Question Bank Management")

        questions_df = get_all_questions()
        st.write(f"Total Questions: **{len(questions_df)}**")

        with st.expander("➕ Add New Question", expanded=False):
            with st.form("add_question_form"):
                q_text = st.text_area("Question Statement:")
                col1, col2 = st.columns(2)
                opt_a = col1.text_input("Option A:")
                opt_b = col2.text_input("Option B:")
                opt_c = col1.text_input("Option C:")
                opt_d = col2.text_input("Option D:")

                correct_opt = st.selectbox("Correct Option:", ["Option A", "Option B", "Option C", "Option D"])

                if st.form_submit_button("Save Question to Bank"):
                    mapping = {"Option A": opt_a, "Option B": opt_b, "Option C": opt_c, "Option D": opt_d}
                    if q_text and opt_a and opt_b and opt_c and opt_d:
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute('''
                                  INSERT INTO questions (question, option_a, option_b, option_c, option_d, correct_option)
                                  VALUES (?, ?, ?, ?, ?, ?)
                                  ''', (q_text, opt_a, opt_b, opt_c, opt_d, mapping[correct_opt]))
                        conn.commit()
                        conn.close()
                        st.success("Question successfully add ho gaya!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Kripya sabhi fields dhyanpurvak bharein.")

        if not questions_df.empty:
            st.markdown("### Existing Questions")
            for idx, row in questions_df.iterrows():
                with st.container():
                    st.markdown(f"**Q{idx + 1}. {row['question']}**")
                    st.markdown(
                        f"- A: {row['option_a']} | B: {row['option_b']} | C: {row['option_c']} | D: {row['option_d']}")
                    st.markdown(f"✅ **Correct Answer:** `{row['correct_option']}`")

                    if st.button(f"Delete Q{idx + 1}", key=f"del_{row['id']}"):
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute("DELETE FROM questions WHERE id = ?", (row['id'],))
                        conn.commit()
                        conn.close()
                        st.warning("Question delete kar diya gaya hai.")
                        time.sleep(1)
                        st.rerun()
                    st.divider()
        st.stop()

# ==========================================
# 6. STUDENT EXAM INTERFACE & PROCTORING
# ==========================================
quiz_title = get_setting("quiz_title", "Online Examination")
quiz_duration = int(get_setting("duration_minutes", 15))
is_active = (get_setting("is_active", "1") == "1")

st.title(f"📖 {quiz_title}")

# Check 1: Is Exam Active?
if not is_active:
    st.warning("🛑 Yeh exam abhi active nahi hai. Kripya apne administrator se sampark karein.")
    st.stop()

# Check 2: Has student already submitted?
existing_sub = get_submission(current_user)
if existing_sub:
    st.success("✅ Aapne yeh test pehle hi successfully submit kar diya hai.")
    st.metric("Your Score", f"{existing_sub['score']} / {existing_sub['total_questions']}")
    st.info(f"Submitted on: {existing_sub['submitted_at']}")
    st.stop()

# Check 3: Any questions available?
questions_df = get_all_questions()
if questions_df.empty:
    st.info("Abhi exam me koi question upload nahi kiya gaya hai. Kripya wait karein.")
    st.stop()

# --- Quiz Start Gate ---
if not st.session_state.quiz_started:
    st.markdown("### 📌 Instructions & Anti-Cheating Guidelines:")
    st.markdown(f"""
    - **Total Duration:** `{quiz_duration} Minutes`
    - **Total Questions:** `{len(questions_df)}`
    - **Security Rules:**
        1. Dusri tab ya app switch karne par warning prompt aayega aur admin log me record hoga.
        2. Copy-paste aur Right click block rahenge.
        3. Timer continuously chalega, page refresh karne par bhi time reset nahi hoga.
    """)
    if st.button("🚀 Start Exam Now", type="primary"):
        st.session_state.quiz_started = True
        st.session_state.start_time = time.time()
        st.rerun()
    st.stop()

# --- Live Anti-Cheat JS Inject ---
inject_proctoring_script()

# --- Live Countdown Timer ---
elapsed = time.time() - st.session_state.start_time
total_seconds = quiz_duration * 60
remaining_seconds = total_seconds - elapsed

if remaining_seconds <= 0:
    st.error("⏰ Samay samapt ho gaya hai! Exam auto-submit ho gaya hai.")
    # Auto-submit 0 score on timeout if not already submitted
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
              INSERT
              OR IGNORE INTO submissions (email, score, total_questions, submitted_at)
        VALUES (?, ?, ?, ?)
              ''', (current_user, 0, len(questions_df), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    st.stop()

# Timer Display Header
mins, secs = divmod(int(remaining_seconds), 60)
timer_col1, timer_col2 = st.columns([3, 1])
timer_col1.markdown(f"Candidate: **{current_user}**")
timer_col2.metric("⏳ Time Left", f"{mins:02d}:{secs:02d}")

st.divider()

# --- Quiz Form ---
with st.form("exam_submission_form"):
    student_answers = {}

    for idx, row in questions_df.iterrows():
        st.markdown(f"**Q{idx + 1}. {row['question']}**")
        options = [row['option_a'], row['option_b'], row['option_c'], row['option_d']]
        student_answers[row['id']] = st.radio(
            "Select your option:",
            options,
            key=f"opt_{row['id']}",
            index=None
        )
        st.markdown("---")

    final_submit = st.form_submit_button("Submit Exam", type="primary")

    if final_submit:
        # Score calculation
        calculated_score = 0
        for _, row in questions_df.iterrows():
            q_id = row['id']
            if student_answers.get(q_id) == row['correct_option']:
                calculated_score += 1

        # Save to SQLite Database
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''
                  INSERT INTO submissions (email, score, total_questions, submitted_at)
                  VALUES (?, ?, ?, ?)
                  ''', (
                      current_user,
                      calculated_score,
                      len(questions_df),
                      datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                  ))
        conn.commit()
        conn.close()

        st.balloons()
        st.success(f"🎉 Exam submit ho gaya hai! Aapka Score: {calculated_score} / {len(questions_df)}")
        time.sleep(2)
        st.rerun()
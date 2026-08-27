import base64
import os
import sqlite3
from datetime import datetime
import pandas as pd
import streamlit as st

# ----------------- PAGE CONFIG -----------------
st.set_page_config(
    page_title="Physics Lab SOP Portal",
    page_icon="🔬",
    layout="wide",
)

DB_FILE = "physics_lab_sop_v3.db"
UPLOAD_DIR = "uploaded_sop_docs"

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# ----------------- DATA SEED -----------------
DEFAULT_STUDENTS = [
    ("Rahul Sharma", "SR1001", "Class 11-A"),
    ("Priya Verma", "SR1002", "Class 11-A"),
    ("Aman Singh", "SR1003", "Class 12-B"),
    ("Sneha Patel", "SR1004", "Class 12-B"),
]

DEFAULT_SOPS = [
    # 1. Lab Access, Roles & General Discipline
    (
        1,
        "1. Lab Access, Roles & General Discipline",
        "Supervised Entry",
        "Guidelines",
        (
            "Students must enter the laboratory only under the supervision of the"
            " Physics Teacher or Lab Assistant. Unauthorized operation of equipment is"
            " strictly prohibited."
        ),
        "Active",
        "Lab Entrance Desk",
        1,
        "",
    ),
    (
        2,
        "1. Lab Access, Roles & General Discipline",
        "Dress Code & Safety Attire",
        "Safety Rule",
        (
            "Closed-toe shoes are mandatory. Secure loose clothing, roll up long"
            " sleeves, and tie back long hair. Keep aisles clear by storing school bags"
            " on designated racks."
        ),
        "Active",
        "Notice Board",
        1,
        "",
    ),
    (
        3,
        "1. Lab Access, Roles & General Discipline",
        "Workplace Boundaries",
        "Floor Protocol",
        (
            "Maintain clear segregation between general workstations, the optical"
            " darkroom section, and the apparatus storage area. Eating and drinking"
            " inside the lab are strictly forbidden."
        ),
        "Active",
        "Workstation Benches",
        1,
        "",
    ),
    # 2. Pre-Lab Briefing, Alignment & Setup
    (
        4,
        "2. Pre-Lab Briefing, Alignment & Setup",
        "Pre-Experiment Briefing",
        "Instructional Guide",
        (
            "Attend the instructional overview regarding experiment theory, circuit"
            " layout, and safety considerations before handling apparatus."
        ),
        "Active",
        "Briefing Zone",
        1,
        "",
    ),
    (
        5,
        "2. Pre-Lab Briefing, Alignment & Setup",
        "Instrument Calibration",
        "Calibration Check",
        (
            "Inspect measuring devices (Vernier Callipers, Screw Gauges, Spherometers,"
            " and Multimeters) for zero error and calibration before recording values."
        ),
        "Active",
        "Measurement Desk",
        1,
        "",
    ),
    (
        6,
        "2. Pre-Lab Briefing, Alignment & Setup",
        "Optical Components Handling",
        "Handling Rule",
        (
            "Hold prisms, lenses, and mirrors only by their frosted edges to avoid"
            " fingerprints; clean them using optical lens paper."
        ),
        "Active",
        "Optics Bench",
        1,
        "",
    ),
    (
        7,
        "2. Pre-Lab Briefing, Alignment & Setup",
        "Mechanical Elements Handling",
        "Handling Rule",
        (
            "Handle slotted weights, pendulums, and pulleys carefully; do not exceed"
            " rated elastic limits or drop weights on benches."
        ),
        "Active",
        "Mechanics Table",
        1,
        "",
    ),
    (
        8,
        "2. Pre-Lab Briefing, Alignment & Setup",
        "Optical Sources & Laser Safety",
        "Safety Standard",
        (
            "Never look directly into laser beams (diffraction/interference setups) or"
            " point them at other individuals."
        ),
        "Active",
        "Darkroom Area",
        1,
        "",
    ),
    # 3. Electrical & Thermal Safety Execution
    (
        9,
        "3. Electrical & Thermal Safety Execution",
        "Mandatory Circuit Inspection",
        "Verification SOP",
        (
            "All circuit connections must be verified and approved by the instructor"
            " before switching on the power supply."
        ),
        "Active",
        "Electrical Benches",
        1,
        "",
    ),
    (
        10,
        "3. Electrical & Thermal Safety Execution",
        "Power-Down Protocol",
        "Safety Standard",
        (
            "Always turn off the power source and disconnect supply lines before"
            " altering components, replacing resistors, or modifying connections."
        ),
        "Active",
        "Circuit Workstations",
        1,
        "",
    ),
    (
        11,
        "3. Electrical & Thermal Safety Execution",
        "Capacitor & High-Voltage Precautions",
        "Hazard Protocol",
        (
            "Safely discharge high-value capacitors prior to handling. Maintain clearance"
            " from high-voltage terminals on induction coils or step-up transformers."
        ),
        "Active",
        "High Voltage Setup",
        1,
        "",
    ),
    (
        12,
        "3. Electrical & Thermal Safety Execution",
        "Thermal Procedures",
        "Hazard Protocol",
        (
            "Never leave Bunsen burners or heating elements unattended during"
            " calorimetry experiments. Use tongs or heat-resistant gloves to handle"
            " heated metal cylinders."
        ),
        "Active",
        "Calorimetry Station",
        1,
        "",
    ),
    # 4. Hazard Management & Emergency Response
    (
        13,
        "4. Hazard Management & Emergency Response",
        "Emergency Power Cut-Off",
        "Emergency SOP",
        (
            "In case of sparking, burning smells, or short circuits, instantly shut down"
            " the main power switch or trip the MCB."
        ),
        "Active",
        "Main MCB Panel",
        1,
        "",
    ),
    (
        14,
        "4. Hazard Management & Emergency Response",
        "Spill & Glass Breakage Protocol",
        "Accident Response",
        (
            "If a thermometer or barometer breaks, report the mercury spill immediately"
            " for proper containment and maximize room ventilation."
        ),
        "Active",
        "Hazard Waste Box",
        1,
        "",
    ),
    (
        15,
        "4. Hazard Management & Emergency Response",
        "First Aid & Safety Readiness",
        "Safety Standard",
        (
            "Ensure First Aid kits, CO2/Class C fire extinguishers, and sand buckets"
            " remain unobstructed. Report all minor burns, cuts, or shocks immediately to"
            " the instructor."
        ),
        "Active",
        "Safety Station 1",
        1,
        "",
    ),
    # 5. Verification, Inventory & Handover
    (
        16,
        "5. Verification, Inventory & Handover",
        "Data Verification",
        "Academic Protocol",
        (
            "Complete the required observation sets, calculations, and graphs, and"
            " obtain teacher verification before dismantling apparatus."
        ),
        "Active",
        "Instructor Signature Desk",
        1,
        "",
    ),
    (
        17,
        "5. Verification, Inventory & Handover",
        "Equipment Return & Cleanup",
        "Inventory SOP",
        (
            "Clean and return all instruments, optical benches, and components to their"
            " designated storage positions in proper working order."
        ),
        "Active",
        "Return Counter",
        1,
        "",
    ),
    (
        18,
        "5. Verification, Inventory & Handover",
        "Defect Reporting & Logbooks",
        "Maintenance Log",
        (
            "Document equipment issues in the lab logbook and mark malfunctioning units"
            " with an 'Out of Order' tag for prompt maintenance."
        ),
        "Active",
        "Logbook Register",
        1,
        "",
    ),
]


# ----------------- DATABASE UTILITIES -----------------
def get_db_connection():
    return sqlite3.connect(DB_FILE)


def init_db():
    conn = get_db_connection()
    c = conn.cursor()

    # SOPs Table
    c.execute(
        """CREATE TABLE IF NOT EXISTS lab_sops (
            sop_id INTEGER PRIMARY KEY,
            section TEXT,
            title TEXT,
            format TEXT,
            sop_guideline TEXT,
            status TEXT,
            remarks TEXT,
            is_published INTEGER,
            file_path TEXT
        )"""
    )

    # Students Roster Table
    c.execute(
        """CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT UNIQUE,
            sr_number TEXT UNIQUE,
            class_section TEXT
        )"""
    )

    c.execute("SELECT COUNT(*) FROM lab_sops")
    if c.fetchone()[0] == 0:
        c.executemany(
            """INSERT INTO lab_sops 
            (sop_id, section, title, format, sop_guideline, status, remarks, is_published, file_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            DEFAULT_SOPS,
        )

    c.execute("SELECT COUNT(*) FROM students")
    if c.fetchone()[0] == 0:
        c.executemany(
            """INSERT INTO students (student_name, sr_number, class_section) VALUES (?, ?, ?)""",
            DEFAULT_STUDENTS,
        )

    conn.commit()
    conn.close()


init_db()


def authenticate_student(name, sr_no):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM students WHERE LOWER(TRIM(student_name)) = LOWER(TRIM(?)) AND TRIM(sr_number) = TRIM(?)",
        (name, sr_no),
    )
    res = c.fetchone()
    conn.close()
    return res


def load_sops(published_only=False):
    conn = get_db_connection()
    query = (
        "SELECT * FROM lab_sops WHERE is_published = 1 ORDER BY sop_id ASC"
        if published_only
        else "SELECT * FROM lab_sops ORDER BY sop_id ASC"
    )
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def update_sop(sop_id, title, guideline, is_published, status, remarks, file_path):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        """UPDATE lab_sops 
           SET title = ?, sop_guideline = ?, is_published = ?, status = ?, remarks = ?, file_path = ?
           WHERE sop_id = ?""",
        (title, guideline, is_published, status, remarks, file_path, sop_id),
    )
    conn.commit()
    conn.close()


def show_pdf_viewer(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode("utf-8")
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf" style="border-radius: 8px; border: 1px solid #ddd;"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
    else:
        st.warning("Attached document not found on server.")


# ----------------- SESSION STATE -----------------
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "user_role" not in st.session_state:
    st.session_state["user_role"] = None
if "user_info" not in st.session_state:
    st.session_state["user_info"] = None

# ----------------- AUTHENTICATION FLOW -----------------
st.sidebar.title("🔐 Physics Lab Access")

if not st.session_state["logged_in"]:
    role_choice = st.sidebar.radio("Select Login Type:", ["Student Login", "Admin Login"])

    if role_choice == "Student Login":
        st.title("🔬 Student Portal Authentication")
        st.caption("Enter your registered Student Name and SR Number (Password) to proceed.")

        with st.form("student_login_form"):
            in_name = st.text_input("Username (Student Full Name):", placeholder="e.g. Rahul Sharma")
            in_sr = st.text_input("Password (SR Number):", type="password", placeholder="e.g. SR1001")
            submit_student = st.form_submit_button("Sign In to Portal", type="primary")

            if submit_student:
                record = authenticate_student(in_name, in_sr)
                if record:
                    st.session_state["logged_in"] = True
                    st.session_state["user_role"] = "Student"
                    st.session_state["user_info"] = {"name": record[1], "sr": record[2], "class": record[3]}
                    st.rerun()
                else:
                    st.error("Invalid Student Name or SR Number. Contact your Physics Teacher if not registered.")

        st.info("💡 Default Demo Credentials:\n- **Username:** Rahul Sharma | **Password:** SR1001\n- **Username:** Priya Verma | **Password:** SR1002")

    else:
        st.title("🛠️ Lab Administrator Login")
        st.caption("Authorized Physics Faculty / Lab Incharge Login.")

        with st.form("admin_login_form"):
            admin_user = st.text_input("Admin Username:", value="admin")
            admin_pass = st.text_input("Admin Password:", type="password")
            submit_admin = st.form_submit_button("Sign In as Administrator", type="primary")

            if submit_admin:
                if admin_user == "admin" and admin_pass == "admin123":
                    st.session_state["logged_in"] = True
                    st.session_state["user_role"] = "Admin"
                    st.session_state["user_info"] = {"name": "Lab Administrator"}
                    st.rerun()
                else:
                    st.error("Invalid Admin Username or Password.")

        st.info("💡 Default Admin Credentials:\n- **Username:** `admin` | **Password:** `admin123`")

else:
    # Top User Banner & Logout
    st.sidebar.success(f"Logged in as: **{st.session_state['user_info']['name']}** ({st.session_state['user_role']})")
    if st.sidebar.button("Logout"):
        st.session_state["logged_in"] = False
        st.session_state["user_role"] = None
        st.session_state["user_info"] = None
        st.rerun()

    # =========================================================================
    # 1. ADMIN DASHBOARD & CONTROLS
    # =========================================================================
    if st.session_state["user_role"] == "Admin":
        st.title("🛠️ Physics Lab SOP Master Admin & Publisher")
        st.caption("Manage standard operating procedures, toggle visibility for students, and upload attachments.")

        adm_tab1, adm_tab2 = st.tabs(["📋 SOP Management & Attachments", "👥 Student Roster Management"])

        with adm_tab1:
            df_all = load_sops(published_only=False)
            total_count = len(df_all)
            pub_count = len(df_all[df_all["is_published"] == 1])
            draft_count = total_count - pub_count

            c1, c2, c3 = st.columns(3)
            c1.metric("Total SOP Entries", total_count)
            c2.metric("Visible to Students (Published)", pub_count)
            c3.metric("Drafts (Hidden)", draft_count)

            st.divider()

            sections_list = ["All Sections"] + list(df_all["section"].unique())
            selected_sec = st.selectbox("Filter by Category:", sections_list)

            filtered_df = df_all if selected_sec == "All Sections" else df_all[df_all["section"] == selected_sec]

            for _, row in filtered_df.iterrows():
                sop_id = int(row["sop_id"])
                current_file = str(row["file_path"]) if row["file_path"] else ""
                status_icon = "🟢 LIVE IN VIEWER" if row["is_published"] == 1 else "⚪ DRAFT (Hidden)"
                file_icon = "📎 [PDF Attached]" if current_file else "📄 [No File]"

                with st.expander(f"SOP #{row['sop_id']} - {row['title']} | {status_icon} | {file_icon}"):
                    with st.form(key=f"edit_form_{sop_id}"):
                        f1, f2, f3 = st.columns([2, 1, 1])
                        with f1:
                            new_title = st.text_input("SOP Title:", value=row["title"])
                        with f2:
                            new_format = st.text_input("Category Tag:", value=row["format"], disabled=True)
                        with f3:
                            is_pub = st.checkbox("✅ Publish to Viewer Portal", value=bool(row["is_published"]), key=f"pub_{sop_id}")

                        new_guideline = st.text_area("SOP Guideline Text:", value=row["sop_guideline"], height=90)

                        f4, f5 = st.columns(2)
                        with f4:
                            new_status = st.selectbox("Compliance Status:", ["Active", "Under Review", "Draft", "Archived"],
                                                      index=0 if row["status"] == "Active" else 1)
                        with f5:
                            new_remarks = st.text_input("Designated Desk / Location:", value=row["remarks"] if row["remarks"] else "")

                        uploaded_file = st.file_uploader(f"Attach Document (PDF/Doc/Image) for SOP #{sop_id}",
                                                         type=["pdf", "png", "jpg", "jpeg", "docx"], key=f"up_{sop_id}")

                        save_btn = st.form_submit_button("Save & Update SOP")
                        if save_btn:
                            file_save_path = current_file
                            if uploaded_file is not None:
                                ext = uploaded_file.name.split(".")[-1]
                                file_save_path = os.path.join(UPLOAD_DIR, f"SOP_{sop_id}_{int(datetime.now().timestamp())}.{ext}")
                                with open(file_save_path, "wb") as f:
                                    f.write(uploaded_file.getbuffer())

                            update_sop(sop_id, new_title, new_guideline, 1 if is_pub else 0, new_status, new_remarks, file_save_path)
                            st.success(f"SOP #{sop_id} '{new_title}' updated successfully!")
                            st.rerun()

                    if current_file and os.path.exists(current_file):
                        st.info(f"Attached: `{os.path.basename(current_file)}`")
                        if current_file.lower().endswith(".pdf"):
                            with st.expander("👁️ Preview PDF Document"):
                                show_pdf_viewer(current_file)

        with adm_tab2:
            st.subheader("Student Authentication Roster")
            conn = get_db_connection()
            students_df = pd.read_sql_query("SELECT * FROM students ORDER BY id ASC", conn)

            st.dataframe(students_df, use_container_width=True)

            st.markdown("##### ➕ Register New Student Credentials")
            with st.form("add_student_form"):
                sc1, sc2, sc3 = st.columns(3)
                with sc1:
                    new_st_name = st.text_input("Student Full Name (Username)*")
                with sc2:
                    new_st_sr = st.text_input("SR Number (Password)*")
                with sc3:
                    new_st_class = st.text_input("Class & Section", value="Class 11-A")

                add_st_btn = st.form_submit_button("Add Student Record")
                if add_st_btn:
                    if new_st_name and new_st_sr:
                        try:
                            c = conn.cursor()
                            c.execute("INSERT INTO students (student_name, sr_number, class_section) VALUES (?, ?, ?)",
                                      (new_st_name.strip(), new_st_sr.strip(), new_st_class.strip()))
                            conn.commit()
                            st.success(f"Student '{new_st_name}' registered successfully with SR Number: {new_st_sr}")
                            conn.close()
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Student Name or SR Number already exists in database.")
                    else:
                        st.error("Please fill both Student Name and SR Number.")
            conn.close()

    # =========================================================================
    # 2. STUDENT / VIEWER PORTAL
    # =========================================================================
    else:
        st.title("🔬 Standard Operating Procedure (SOP) – Physics Laboratory")
        st.markdown(f"**Student:** {st.session_state['user_info']['name']} | **SR Number:** `{st.session_state['user_info']['sr']}` | **Batch:** `{st.session_state['user_info']['class']}`")
        st.caption("Official Safety Protocols, Apparatus Handling Guidelines & Operational Standards")

        df_live = load_sops(published_only=True)

        if df_live.empty:
            st.info("No SOP protocols are currently published for viewing.")
        else:
            search_query = st.text_input("🔍 Search Protocols, Apparatus Rules, or Safety Guidelines:")
            if search_query:
                df_live = df_live[
                    df_live["title"].str.contains(search_query, case=False)
                    | df_live["sop_guideline"].str.contains(search_query, case=False)
                    | df_live["section"].str.contains(search_query, case=False)
                ]

            available_sections = sorted(df_live["section"].unique())
            tabs = st.tabs(available_sections)

            for i, sec_name in enumerate(available_sections):
                with tabs[i]:
                    sec_records = df_live[df_live["section"] == sec_name]
                    st.subheader(f"{sec_name}")

                    for _, sop_item in sec_records.iterrows():
                        with st.container(border=True):
                            h1, h2 = st.columns([3, 1])
                            with h1:
                                st.markdown(f"#### 📑 #{sop_item['sop_id']} {sop_item['title']}")
                            with h2:
                                st.markdown(f"**Classification:** `{sop_item['format']}`")

                            st.markdown(f"**📋 Operational Guidelines:**\n{sop_item['sop_guideline']}")

                            f1, f2 = st.columns([2, 2])
                            with f1:
                                st.caption(f"📍 **Designated Location:** {sop_item['remarks']}")
                            with f2:
                                st.caption(f"⚡ **Status:** `{sop_item['status']}`")

                            file_path = str(sop_item["file_path"]) if sop_item["file_path"] else ""
                            if file_path and os.path.exists(file_path):
                                st.divider()
                                cb1, cb2 = st.columns([1, 3])
                                with open(file_path, "rb") as f:
                                    file_bytes = f.read()
                                    file_name = os.path.basename(file_path)

                                with cb1:
                                    st.download_button(
                                        label="📥 Download Attached File",
                                        data=file_bytes,
                                        file_name=file_name,
                                        mime="application/pdf",
                                        key=f"dl_st_{sop_item['sop_id']}",
                                    )

                                if file_path.lower().endswith(".pdf"):
                                    with st.expander(f"👁️ View Document: {sop_item['title']} (In-Browser Viewer)"):
                                        show_pdf_viewer(file_path)
                                elif file_path.lower().endswith((".png", ".jpg", ".jpeg")):
                                    with st.expander("👁️ View Attached Diagram / Schematic"):
                                        st.image(file_path, use_container_width=True)

            st.divider()
            csv_data = df_live.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Export Full SOP Standards (CSV)",
                data=csv_data,
                file_name="Physics_Lab_SOP_Standards.csv",
                mime="text/csv",
            )

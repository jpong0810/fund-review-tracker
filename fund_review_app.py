import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

DB = "fund_checklist_table.db"
TODAY = lambda: datetime.today().strftime("%Y-%m-%d")

STEPS = [
    ("step2_outreach", "2) Optional Outreach"),
    ("step3_analyst",  "3) Analyst Review"),
    ("step4_vp",       "4) VP Review"),
    ("step5_partner",  "5) Partner Confirmation"),
    ("step6_feedback", "6) Feedback Call"),
    ("step7_rejected", "7) Rejected"),
]

st.set_page_config(page_title="Fund Checklist", layout="wide")

# ---- Styling ----
st.markdown("""
<style>
.block-container {padding-top: 0.5rem; max-width: 1100px;}
.dataframe td, .dataframe th {font-size: 0.9rem;}
</style>
""", unsafe_allow_html=True)

# ---- DB helpers ----
def conn():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():
    with conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS funds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ord INTEGER DEFAULT 1000,
                fund_name TEXT NOT NULL,
                assigned_date TEXT NOT NULL,
                step2_outreach INTEGER DEFAULT 0,
                step3_analyst  INTEGER DEFAULT 0,
                step4_vp       INTEGER DEFAULT 0,
                step5_partner  INTEGER DEFAULT 0,
                step6_feedback INTEGER DEFAULT 0,
                step7_rejected INTEGER DEFAULT 0,
                step2_outreach_date TEXT,
                step3_analyst_date  TEXT,
                step4_vp_date       TEXT,
                step5_partner_date  TEXT,
                step6_feedback_date TEXT,
                step7_rejected_date TEXT
            )
        """)
        c.commit()

def load_df():
    with conn() as c:
        return pd.read_sql_query("SELECT * FROM funds ORDER BY ord, id", c)

def add_fund(name, assigned):
    with conn() as c:
        max_ord = c.execute("SELECT COALESCE(MAX(ord), 0) FROM funds").fetchone()[0] or 0
        c.execute(
            "INSERT INTO funds (ord, fund_name, assigned_date) VALUES (?,?,?)",
            (max_ord + 10, name.strip(), assigned)
        )
        c.commit()

def update_field(row_id, field, value):
    with conn() as c:
        c.execute(f"UPDATE funds SET {field}=? WHERE id=?", (value, row_id))
        c.commit()

def delete_row(row_id):
    with conn() as c:
        c.execute("DELETE FROM funds WHERE id=?", (row_id,))
        c.commit()

def stamp_if_new(old_val, new_val, old_date):
    if (not old_val) and bool(new_val) and (not old_date):
        return TODAY()
    return old_date

# ---- App ----
init_db()

st.markdown("## ✅ Fund Review Checklist")

# Add fund form
with st.form("add_fund", clear_on_submit=True):
    c1, c2, c3 = st.columns([3,2,1])
    fund_name = c1.text_input("Fund Name")
    assigned = c2.date_input("Assigned Date", value=pd.to_datetime("today")).strftime("%Y-%m-%d")
    submitted = c3.form_submit_button("Add")
    if submitted and fund_name.strip():
        add_fund(fund_name, assigned)
        st.success("Added fund.")
        st.rerun()

df = load_df()
if df.empty:
    st.info("No funds yet. Add your first fund above.")
    st.stop()

# Ensure correct dtypes
df["assigned_date"] = pd.to_datetime(df["assigned_date"], errors="coerce").dt.date
for col, _ in STEPS:
    df[col] = df[col].astype(bool)

# Display table with checkboxes
for idx, row in df.iterrows():
    cols = st.columns([0.5, 2, 1] + [1]*len(STEPS) + [0.7])
    # Order
    new_ord = cols[0].number_input("", value=int(row["ord"]), step=1, label_visibility="collapsed", key=f"ord_{row['id']}")
    if new_ord != row["ord"]:
        update_field(row["id"], "ord", new_ord)
        st.experimental_rerun()

    # Fund name
    new_name = cols[1].text_input("", value=row["fund_name"], label_visibility="collapsed", key=f"name_{row['id']}")
    if new_name != row["fund_name"]:
        update_field(row["id"], "fund_name", new_name)
        st.experimental_rerun()

    # Assigned date
    new_assigned = cols[2].date_input("", value=row["assigned_date"], label_visibility="collapsed", key=f"assigned_{row['id']}")
    if new_assigned != row["assigned_date"]:
        update_field(row["id"], "assigned_date", str(new_assigned))
        st.experimental_rerun()

    # Steps
    for step_idx, (colname, label) in enumerate(STEPS):
        tooltip = f"Completed: {row[colname + '_date']}" if row[colname + '_date'] else "Not completed yet"
        checked = cols[3+step_idx].checkbox(label, value=row[colname], help=tooltip, key=f"{colname}_{row['id']}")
        if checked != row[colname]:
            # stamp date if first time checked
            date_stamp = stamp_if_new(row[colname], checked, row[colname + "_date"])
            update_field(row["id"], colname, int(checked))
            update_field(row["id"], colname + "_date", date_stamp)
            st.experimental_rerun()

    # Delete button (only allowed if Rejected is checked)
    if row["step7_rejected"]:
        if cols[-1].button("🗑️", key=f"del_{row['id']}", help="Delete this rejected fund"):
            delete_row(row["id"])
            st.experimental_rerun()

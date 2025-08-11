import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date

DB = "fund_checklist.db"

STEPS = [
    ("step2_outreach", "2) Optional Outreach"),
    ("step3_analyst", "3) Analyst Review"),
    ("step4_vp", "4) VP Review"),
    ("step5_partner", "5) Partner Confirmation"),
    ("step6_feedback", "6) Feedback Call"),
    ("step7_rejected", "7) Rejected"),
]

st.set_page_config(page_title="Fund Checklist", layout="wide")

# ---------- DB helpers ----------
def conn():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():
    with conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS funds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fund_name TEXT NOT NULL,
                assigned_date TEXT NOT NULL,
                step2_outreach TEXT,
                step3_analyst TEXT,
                step4_vp TEXT,
                step5_partner TEXT,
                step6_feedback TEXT,
                step7_rejected TEXT
            )
        """)
        c.commit()

def add_fund(name:str, assigned:str):
    with conn() as c:
        c.execute("""INSERT INTO funds
                     (fund_name, assigned_date)
                     VALUES (?, ?)""", (name.strip(), assigned))
        c.commit()

def get_funds_df():
    with conn() as c:
        return pd.read_sql_query("SELECT * FROM funds ORDER BY id DESC", c)

def set_step_date(row_id:int, col:str, value:str):
    with conn() as c:
        c.execute(f"UPDATE funds SET {col}=? WHERE id=?", (value, row_id))
        c.commit()

def reset_steps(row_id:int):
    with conn() as c:
        sets = ",".join([f"{col}=NULL" for col,_ in STEPS])
        c.execute(f"UPDATE funds SET {sets} WHERE id=?", (row_id,))
        c.commit()

def today():
    return datetime.today().strftime("%Y-%m-%d")

# ---------- App ----------
init_db()
st.title("✅ Simple Fund Review Checklist")

# --- Add a fund ---
with st.expander("➕ Add a fund", expanded=True):
    c1, c2 = st.columns([2,1])
    fund_name = c1.text_input("Fund Name")
    assigned_date = c2.date_input("Assigned Date", value=pd.to_datetime("today")).strftime("%Y-%m-%d")
    if st.button("Add", type="primary", disabled=(not fund_name.strip())):
        add_fund(fund_name, assigned_date)
        st.success("Fund added. Refresh the page if it doesn’t appear below.")

# --- Data ---
df = get_funds_df()
if df.empty:
    st.info("No funds yet. Add one above.")
    st.stop()

# --- Pick a fund to update ---
st.subheader("Update a fund")
left, right = st.columns([2,1])
with left:
    choices = {f"{r['fund_name']} (assigned {r['assigned_date']})": int(r["id"]) for _, r in df.iterrows()}
    selection = st.selectbox("Select fund", list(choices.keys()))
    fund_id = choices[selection]

row = df[df["id"] == fund_id].iloc[0]

with right:
    if st.button("Reset all step dates for this fund"):
        reset_steps(int(fund_id))
        st.warning("All step dates cleared for this fund. (Assigned date stays.)")

# --- Checklist (one-way date stamping) ---
st.markdown("### Steps")
cols = st.columns(3)
for i, (colname, label) in enumerate(STEPS):
    with cols[i % 3]:
        already_done = pd.notna(row[colname]) and str(row[colname]).strip() != ""
        checked = st.checkbox(label, value=already_done, key=colname)
        # One-way: if turning from unchecked -> checked and no date recorded, stamp today
        if checked and not already_done:
            set_step_date(int(fund_id), colname, today())
        # Do NOT clear dates if user unchecks; we keep the original completion date

# Refresh snapshot
df = get_funds_df()
row = df[df["id"] == fund_id].iloc[0]

# --- Readable table of dates ---
st.markdown("### Dates")
dates = {
    "Fund Name": row["fund_name"],
    "Assigned": row["assigned_date"],
    "2) Optional Outreach": row["step2_outreach"] or "",
    "3) Analyst Review": row["step3_analyst"] or "",
    "4) VP Review": row["step4_vp"] or "",
    "5) Partner Confirmation": row["step5_partner"] or "",
    "6) Feedback Call": row["step6_feedback"] or "",
    "7) Rejected": row["step7_rejected"] or "",
}
st.table(pd.DataFrame([dates]).T.rename(columns={0:"Date"}))

st.divider()

# --- All funds overview + export ---
st.subheader("All funds")
pretty = df.rename(columns={
    "fund_name":"Fund",
    "assigned_date":"Assigned",
    "step2_outreach":"2) Outreach",
    "step3_analyst":"3) Analyst",
    "step4_vp":"4) VP",
    "step5_partner":"5) Partner",
    "step6_feedback":"6) Feedback",
    "step7_rejected":"7) Rejected",
})
st.dataframe(pretty[["id","Fund","Assigned","2) Outreach","3) Analyst","4) VP","5) Partner","6) Feedback","7) Rejected"]], use_container_width=True)

st.download_button(
    "⬇️ Export to CSV",
    pretty.to_csv(index=False).encode("utf-8"),
    file_name="fund_checklist_export.csv",
    mime="text/csv"
)


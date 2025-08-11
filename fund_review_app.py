import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date

# -------------------- Config --------------------
DB = "fund_checklist.db"
STEPS = [
    ("step2_outreach", "2) Optional Outreach"),
    ("step3_analyst",  "3) Analyst Review"),
    ("step4_vp",       "4) VP Review"),
    ("step5_partner",  "5) Partner Confirmation"),
    ("step6_feedback", "6) Feedback Call"),
    ("step7_rejected", "7) Rejected"),
]

st.set_page_config(page_title="Fund Checklist", layout="wide")

# -------------------- Light styling --------------------
st.markdown("""
<style>
/* cleaner page widths */
.block-container {padding-top: 1rem; max-width: 1200px;}
/* section cards */
.card {background: #ffffff; border: 1px solid #e6e6ef; border-radius: 12px; padding: 1rem 1.2rem; margin-bottom: 0.8rem;}
.card h4 {margin: 0 0 .4rem 0;}
.small {color:#6b6b6b; font-size:0.9rem;}
.pill {display:inline-block; padding:.2rem .55rem; border-radius:999px; border:1px solid #e3e3ee; margin:.15rem .25rem .15rem 0; font-size:0.85rem;}
.pill.done {background:#eefbf1; border-color:#c6efce;}
.pill.todo {background:#f7f7fb;}
.kpi {font-weight:600; font-size:1.1rem;}
</style>
""", unsafe_allow_html=True)

# -------------------- DB helpers --------------------
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
                step3_analyst  TEXT,
                step4_vp       TEXT,
                step5_partner  TEXT,
                step6_feedback TEXT,
                step7_rejected TEXT
            )
        """)
        c.commit()

def add_fund(name: str, assigned: str):
    with conn() as c:
        c.execute("""INSERT INTO funds (fund_name, assigned_date) VALUES (?,?)""",
                  (name.strip(), assigned))
        c.commit()

def get_funds_df():
    with conn() as c:
        return pd.read_sql_query("SELECT * FROM funds ORDER BY id DESC", c)

def set_step_date(row_id: int, col: str, value: str):
    with conn() as c:
        c.execute(f"UPDATE funds SET {col}=? WHERE id=?", (value, row_id))
        c.commit()

def reset_steps(row_id: int):
    with conn() as c:
        sets = ",".join([f"{col}=NULL" for col,_ in STEPS])
        c.execute(f"UPDATE funds SET {sets} WHERE id=?", (row_id,))
        c.commit()

def today() -> str:
    return datetime.today().strftime("%Y-%m-%d")

# -------------------- App --------------------
init_db()

# Header
left_h, right_h = st.columns([1,2])
with left_h:
    st.markdown("## ✅ Fund Review Checklist")
with right_h:
    st.markdown(
        "<div class='small'>Add a fund (name + assigned date). "
        "Check boxes as you complete steps — we stamp the date once and keep it.</div>",
        unsafe_allow_html=True
    )

# Layout: Sidebar = add/select; Main = checklist + overview
with st.sidebar:
    st.markdown("### ➕ Add a fund")
    fund_name = st.text_input("Fund Name")
    assigned_date = st.date_input("Assigned Date", value=pd.to_datetime('today')).strftime("%Y-%m-%d")
    st.caption("Tip: usually today's date.")
    add_disabled = not fund_name.strip()
    if st.button("Add Fund", type="primary", disabled=add_disabled):
        add_fund(fund_name, assigned_date)
        st.success("Fund added. Select it below to update steps.")

    st.markdown("---")

    df_all = get_funds_df()
    if df_all.empty:
        st.info("No funds yet. Add your first one above.")
    else:
        options = {f"{r['fund_name']}  •  assigned {r['assigned_date']}": int(r['id']) for _, r in df_all.iterrows()}
        selected_label = st.selectbox("Select a fund", list(options.keys()))
        fund_id = options[selected_label]

# Stop early if no data
if df_all.empty:
    st.stop()

row = df_all[df_all["id"] == fund_id].iloc[0]

# -------------------- Progress + Pills --------------------
done_count = sum(1 for col,_ in STEPS if pd.notna(row[col]) and str(row[col]).strip() != "")
progress = int(round((done_count/len(STEPS))*100, 0))
pcol1, pcol2, pcol3 = st.columns([2,1,1])
with pcol1:
    st.markdown(f"<div class='card'><h4>📊 Progress</h4><div class='kpi'>{progress}% complete</div></div>", unsafe_allow_html=True)
with pcol2:
    st.markdown(f"<div class='card'><h4>🗂️ Fund</h4><div class='kpi'>{row['fund_name']}</div><div class='small'>Assigned {row['assigned_date']}</div></div>", unsafe_allow_html=True)
with pcol3:
    if st.button("Reset all step dates", help="Clears all completion dates for this fund (does not remove the fund)."):
        reset_steps(int(fund_id))
        st.warning("All step dates cleared for this fund. Reload if you don't see it update.")

st.progress(progress/100)

# Status pills
pill_html = ""
for col, label in STEPS:
    dt = (row[col] or "").strip() if pd.notna(row[col]) else ""
    if dt:
        pill_html += f"<span class='pill done'>{label}: {dt}</span>"
    else:
        pill_html += f"<span class='pill todo'>{label}: —</span>"
st.markdown(f"<div class='card'>{pill_html}</div>", unsafe_allow_html=True)

# -------------------- Checklist --------------------
st.markdown("#### ✔️ Check steps as you go")
grid = st.columns(3)
for i, (colname, label) in enumerate(STEPS):
    with grid[i % 3]:
        # Already completed?
        already_done = pd.notna(row[colname]) and str(row[colname]).strip() != ""
        # Checkbox shows checked if already done; starts unchecked otherwise
        checked = st.checkbox(label, value=already_done, key=f"{colname}_{fund_id}")
        # One-way date stamping: record today's date the first time it's checked
        if checked and not already_done:
            set_step_date(int(fund_id), colname, today())

st.markdown("---")

# -------------------- Overview table + export --------------------
st.markdown("#### 📒 All funds (read-only)")
pretty = df_all.rename(columns={
    "fund_name":"Fund",
    "assigned_date":"Assigned",
    "step2_outreach":"2) Outreach",
    "step3_analyst":"3) Analyst",
    "step4_vp":"4) VP",
    "step5_partner":"5) Partner",
    "step6_feedback":"6) Feedback",
    "step7_rejected":"7) Rejected",
})
st.dataframe(pretty[["id","Fund","Assigned","2) Outreach","3) Analyst","4) VP","5) Partner","6) Feedback","7) Rejected"]],
             use_container_width=True, hide_index=True)

st.download_button(
    "⬇️ Export to CSV",
    pretty.to_csv(index=False).encode("utf-8"),
    file_name="fund_checklist_export.csv",
    mime="text/csv"
)



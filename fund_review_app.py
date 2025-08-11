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
st.markdown('''
<style>
.block-container {padding-top: 1rem; max-width: 1200px;}
.card {background:#fff;border:1px solid #e6e6ef;border-radius:12px;padding:1rem 1.2rem;margin:.6rem 0;}
h2, h3 {margin: .25rem 0;}
.small {color:#6b6b6b;font-size:.9rem;}
</style>''', unsafe_allow_html=True)

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
        df = pd.read_sql_query("SELECT * FROM funds ORDER BY ord, id", c)
    return df

def add_fund(name, assigned):
    with conn() as c:
        cur = c.execute("SELECT COALESCE(MAX(ord), 0) FROM funds")
        max_ord = cur.fetchone()[0] or 0
        c.execute("""INSERT INTO funds (ord, fund_name, assigned_date) VALUES (?,?,?)""",
                  (max_ord + 10, name.strip(), assigned))
        c.commit()

def update_row(row):
    with conn() as c:
        cols = [k for k in row.keys() if k != "id"]
        set_expr = ",".join([f"{k}=?" for k in cols])
        c.execute(f"UPDATE funds SET {set_expr} WHERE id=?", [row[k] for k in cols] + [row["id"]])
        c.commit()

def delete_rows(ids):
    if not ids: 
        return
    with conn() as c:
        qmarks = ",".join(["?"]*len(ids))
        c.execute(f"DELETE FROM funds WHERE id IN ({qmarks})", ids)
        c.commit()

def stamp_if_new(old_val, new_val, old_date):
    # Stamp TODAY only if changed from 0 -> 1 and there was no date
    if (not old_val) and bool(new_val) and (not old_date):
        return TODAY()
    return old_date

# ---- App ----
init_db()

st.markdown("## ✅ Fund Review Checklist")
st.markdown("""<div class='small'>Add a fund (name + date). Check boxes as you complete steps — we stamp the date the first time and keep it. Edit the 'Order' number to rearrange rows. Check 'Delete' on rejected rows and click 'Save changes'.</div>""", unsafe_allow_html=True)

# Add fund inline
with st.form("add_fund", clear_on_submit=True):
    c1, c2, c3 = st.columns([3,2,1])
    fund_name = c1.text_input("Fund Name")
    assigned = c2.date_input("Assigned Date", value=pd.to_datetime("today")).strftime("%Y-%m-%d")
    submitted = c3.form_submit_button("Add")
    if submitted and fund_name.strip():
        add_fund(fund_name, assigned)
        st.success("Added fund.")

# Load current
df = load_df()
if df.empty:
    st.info("No funds yet. Add your first fund above.")
    st.stop()

# Build an editable view DataFrame
view_cols = ["id","ord","fund_name","assigned_date"]
for col, _ in STEPS:
    view_cols.append(col)
    view_cols.append(col + "_date")
view_cols.append("Delete")

# Compute the view
view = df.copy()
view["Delete"] = False

# Configure columns for data_editor
col_cfg = {
    "ord": st.column_config.NumberColumn("Order", help="Type numbers; lower comes first", step=1),
    "fund_name": st.column_config.TextColumn("Fund Name"),
    "assigned_date": st.column_config.DateColumn("Assigned"),
}
for col, label in STEPS:
    col_cfg[col] = st.column_config.CheckboxColumn(label)
    col_cfg[col + "_date"] = st.column_config.TextColumn(label.replace(")", " date)"), disabled=True)
col_cfg["Delete"] = st.column_config.CheckboxColumn("Delete (only if Rejected is checked)")

st.markdown("### Your funds")
edited = st.data_editor(
    view[view_cols],
    column_config=col_cfg,
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    key="editor"
)

# Save and apply changes
cL, cM, cR = st.columns([1,1,3])
save_clicked = cL.button("💾 Save changes", type="primary")
del_clicked = cM.button("🗑️ Delete all rows marked 'Delete'")

if save_clicked or del_clicked:
    # Determine deletions first
    ids_to_delete = [int(r["id"]) for _, r in edited.iterrows() if bool(r.get("Delete")) and bool(r.get("step7_rejected"))]
    if del_clicked and ids_to_delete:
        delete_rows(ids_to_delete)
        st.success(f"Deleted {len(ids_to_delete)} rejected fund(s).")
        st.experimental_rerun()

    # Merge updates
    updates = []
    orig = df.set_index("id")
    for _, r in edited.iterrows():
        rid = int(r["id"])
        if rid in ids_to_delete:
            continue
        base = orig.loc[rid].to_dict()
        new = {
            "id": rid,
            "ord": int(r["ord"]),
            "fund_name": str(r["fund_name"]).strip(),
            "assigned_date": str(r["assigned_date"]),
        }
        # Steps + date-stamps
        for col, _ in STEPS:
            new_val = 1 if bool(r[col]) else 0
            old_val = int(base[col])
            old_date = (base[col + "_date"] or "")
            stamped = stamp_if_new(old_val, new_val, old_date)
            new[col] = new_val
            new[col + "_date"] = stamped
        updates.append(new)

    for row in updates:
        update_row(row)

    st.success("Saved.")
    st.experimental_rerun()

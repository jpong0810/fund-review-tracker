import streamlit as st
import pandas as pd
from datetime import datetime, date
import sqlite3
from contextlib import closing

# ------------------------------
# Config
# ------------------------------
STAGES = [
    "1 - Assigned",
    "2 - Optional Outreach",
    "3 - Analyst Review",
    "4 - VP Review",
    "5 - Partner Confirmation",
    "6 - Feedback Call",
    "7 - Rejected"
]
PCT_MAP = {
    "1 - Assigned": 0.10,
    "2 - Optional Outreach": 0.20,
    "3 - Analyst Review": 0.40,
    "4 - VP Review": 0.60,
    "5 - Partner Confirmation": 0.80,
    "6 - Feedback Call": 0.90,
    "7 - Rejected": 1.00
}

DATE_STAMP_FOR_STAGE = {
    "3 - Analyst Review": "analyst_review_date",
    "4 - VP Review": "vp_review_date",
    "5 - Partner Confirmation": "partner_confirm_date",
    "6 - Feedback Call": "feedback_call_date",
    "7 - Rejected": "rejected_date",
}

DB_PATH = "fund_reviews.db"

st.set_page_config(page_title="Fund Review Tracker", layout="wide")

# ------------------------------
# DB Helpers
# ------------------------------
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    with get_conn() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS funds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fund_id TEXT,
            fund_name TEXT,
            gp_name TEXT,
            vintage_strategy TEXT,
            analyst TEXT,
            vp TEXT,
            partner TEXT,
            stage TEXT,
            assigned_date TEXT,
            outreach_done INTEGER,
            outreach_contact_name TEXT,
            outreach_contact_email TEXT,
            analyst_review_date TEXT,
            vp_review_date TEXT,
            partner_confirm_date TEXT,
            feedback_call_date TEXT,
            rejected_date TEXT,
            notes TEXT,
            due_date TEXT
        )
        """)
        conn.commit()

def add_fund(record: dict):
    cols = ",".join(record.keys())
    placeholders = ",".join(["?"] * len(record))
    with get_conn() as conn:
        conn.execute(f"INSERT INTO funds ({cols}) VALUES ({placeholders})", list(record.values()))
        conn.commit()

def query_df(sql: str, params=()):
    with closing(get_conn()) as conn, closing(conn.cursor()) as cur:
        df = pd.read_sql_query(sql, conn, params=params)
    return df

def execute(sql: str, params=()):
    with get_conn() as conn:
        conn.execute(sql, params)
        conn.commit()

def update_stage(row_id: int, new_stage: str):
    execute("UPDATE funds SET stage = ? WHERE id = ?", (new_stage, row_id))
    # auto date-stamp certain stages
    if new_stage in DATE_STAMP_FOR_STAGE:
        col = DATE_STAMP_FOR_STAGE[new_stage]
        execute(f"UPDATE funds SET {col}=? WHERE id=?", (today_str(), row_id))

def update_field(row_id: int, field: str, value):
    execute(f"UPDATE funds SET {field}=? WHERE id=?", (value, row_id))

def delete_fund(row_id: int):
    execute("DELETE FROM funds WHERE id=?", (row_id,))

def today_str():
    return datetime.today().strftime("%Y-%m-%d")

# ------------------------------
# Derived helpers
# ------------------------------
def load_data():
    return query_df("SELECT * FROM funds ORDER BY id DESC")

def pct_complete(stage: str) -> int:
    return int(round(PCT_MAP.get(stage, 0) * 100, 0))

def days_since(dstr: str) -> str:
    if not dstr:
        return ""
    try:
        return (date.today() - pd.to_datetime(dstr).date()).days
    except Exception:
        return ""

def next_action(stage: str) -> str:
    if stage == "7 - Rejected":
        return "None (Closed)"
    hints = {
        "1 - Assigned": "Consider outreach if needed",
        "2 - Optional Outreach": "Move to Analyst Review when info sufficient",
        "3 - Analyst Review": "Advance to VP Review",
        "4 - VP Review": "Send to Partner for confirmation",
        "5 - Partner Confirmation": "Schedule feedback call w/ GP or placement",
        "6 - Feedback Call": "Decide: Reject or proceed to next internal step"
    }
    return hints.get(stage, "")

# ------------------------------
# UI
# ------------------------------
init_db()
st.title("🗂️ Fund Review Tracker")

# ---- Add new fund
with st.expander("➕ Add a new fund (Step 1: Assigned)", expanded=True):
    with st.form("new_fund"):
        c1, c2, c3 = st.columns(3)
        fund_id = c1.text_input("Fund ID")
        fund_name = c2.text_input("Fund Name")
        gp_name = c3.text_input("GP / Placement Agent")

        c4, c5, c6 = st.columns(3)
        vintage_strategy = c4.text_input("Vintage / Strategy")
        analyst = c5.text_input("Owner (Analyst)")
        vp = c6.text_input("Owner (VP)")

        partner = st.text_input("Owner (Partner)")
        stage = st.selectbox("Status (Stage)", STAGES, index=0)
        assigned_date = st.date_input("Assigned Date", pd.to_datetime("today")).strftime("%Y-%m-%d")

        outreach_done = st.checkbox("Optional Outreach Done?")
        c7, c8 = st.columns(2)
        outreach_contact_name = c7.text_input("Outreach Contact Name")
        outreach_contact_email = c8.text_input("Outreach Contact Email")

        due_date = st.date_input("Due Date", pd.to_datetime("today")).strftime("%Y-%m-%d")
        notes = st.text_area("Notes / Links")

        submitted = st.form_submit_button("Add Fund")
        if submitted:
            add_fund({
                "fund_id": fund_id.strip(),
                "fund_name": fund_name.strip(),
                "gp_name": gp_name.strip(),
                "vintage_strategy": vintage_strategy.strip(),
                "analyst": analyst.strip(),
                "vp": vp.strip(),
                "partner": partner.strip(),
                "stage": stage,
                "assigned_date": assigned_date,
                "outreach_done": int(outreach_done),
                "outreach_contact_name": outreach_contact_name.strip(),
                "outreach_contact_email": outreach_contact_email.strip(),
                "analyst_review_date": None,
                "vp_review_date": None,
                "partner_confirm_date": None,
                "feedback_call_date": None,
                "rejected_date": None,
                "notes": notes,
                "due_date": due_date
            })
            st.success("Fund added.")

st.divider()

# ---- Filters
df = load_data()
left, mid1, mid2, right = st.columns([2,1,1,2])
with left:
    stage_filter = st.multiselect("Filter: Stage", STAGES, default=STAGES)
with mid1:
    analyst_filter = st.text_input("Filter: Analyst")
with mid2:
    vp_filter = st.text_input("Filter: VP")
with right:
    query = st.text_input("Search: Fund / GP / Fund ID")

if df.empty:
    st.info("No funds yet. Add one above to get started.")
    st.stop()

mask = df["stage"].isin(stage_filter)
if analyst_filter:
    mask &= df["analyst"].str.contains(analyst_filter, case=False, na=False)
if vp_filter:
    mask &= df["vp"].str.contains(vp_filter, case=False, na=False)
if query:
    q = query.strip()
    mask &= (
        df["fund_name"].str.contains(q, case=False, na=False) |
        df["gp_name"].str.contains(q, case=False, na=False) |
        df["fund_id"].str.contains(q, case=False, na=False)
    )

view = df[mask].copy()
view["% Complete"] = view["stage"].apply(pct_complete)
view["Days Since Assigned"] = view["assigned_date"].apply(days_since)
view["Next Action"] = view["stage"].apply(next_action)

# ---- Summary
st.subheader("Summary")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total funds (filtered)", len(view))
c2.metric("In Review (not Rejected)", int((view["stage"] != "7 - Rejected").sum()))
avg_days = pd.to_numeric(view["Days Since Assigned"], errors="coerce").dropna()
c3.metric("Avg days since assigned", int(avg_days.mean()) if len(avg_days) else 0)
c4.metric("Median % complete", int(view["% Complete"].median()) if not view.empty else 0)

st.caption("Tip: use the ‘Manage’ panel below to advance stages—key milestones are date-stamped automatically.")

# ---- Pipeline table
st.subheader("Pipeline")
show_cols = ["id","fund_id","fund_name","gp_name","stage","% Complete","Days Since Assigned","analyst","vp","partner","due_date","Next Action"]
st.dataframe(view[show_cols], use_container_width=True, hide_index=True)

# ---- Kanban-like swimlanes (read-only)
with st.expander("📋 Stage swimlanes (read-only)", expanded=False):
    cols = st.columns(len(STAGES))
    for idx, stg in enumerate(STAGES):
        with cols[idx]:
            st.markdown(f"**{stg}**")
            sub = view[view["stage"] == stg][["fund_name","gp_name","analyst","vp","due_date"]]
            if sub.empty:
                st.write("—")
            else:
                for _, r in sub.iterrows():
                    st.write(f"- {r['fund_name']}  \n  _{r['gp_name']}_  \n  Analyst: {r['analyst'] or '—'} | VP: {r['vp'] or '—'} | Due: {r['due_date'] or '—'}")

st.divider()

# ---- Manage panel
st.subheader("Manage a fund")
min_id, max_id = int(df["id"].min()), int(df["id"].max())
row_id = st.number_input("Row ID", min_value=min_id, max_value=max_id, step=1)

if row_id:
    row = df[df["id"] == int(row_id)]
    if row.empty:
        st.warning("Invalid row id.")
        st.stop()
    r = row.iloc[0]
    st.write(f"**Selected:** {r['fund_name']} — {r['gp_name']}  |  Stage: {r['stage']}")

    a, b, c = st.columns(3)
    with a:
        new_stage = st.selectbox("Advance Stage", STAGES, index=STAGES.index(r["stage"]))
        if st.button("Update Stage"):
            update_stage(int(row_id), new_stage)
            st.success("Stage updated — refresh (R) if the table hasn’t updated yet.")

    with b:
        outreach = st.checkbox("Outreach done?", value=bool(r["outreach_done"]))
        if st.button("Update Outreach"):
            update_field(int(row_id), "outreach_done", int(outreach))
            st.success("Outreach updated.")

    with c:
        if st.button("Delete Fund", type="secondary"):
            delete_fund(int(row_id))
            st.warning("Fund deleted.")

    st.markdown("### Edit fields")
    c1, c2, c3 = st.columns(3)
    nf_name = c1.text_input("Fund Name", value=r["fund_name"] or "")
    nf_gp = c2.text_input("GP / Placement Agent", value=r["gp_name"] or "")
    nf_vs = c3.text_input("Vintage / Strategy", value=r["vintage_strategy"] or "")
    c4, c5, c6 = st.columns(3)
    nf_analyst = c4.text_input("Owner (Analyst)", value=r["analyst"] or "")
    nf_vp = c5.text_input("Owner (VP)", value=r["vp"] or "")
    nf_partner = c6.text_input("Owner (Partner)", value=r["partner"] or "")
    c7, c8 = st.columns(2)
    nf_due = c7.text_input("Due Date (YYYY-MM-DD)", value=r["due_date"] or "")
    nf_notes = c8.text_area("Notes / Links", value=r["notes"] or "")

    if st.button("Save Edits"):
        update_field(int(row_id), "fund_name", nf_name.strip())
        update_field(int(row_id), "gp_name", nf_gp.strip())
        update_field(int(row_id), "vintage_strategy", nf_vs.strip())
        update_field(int(row_id), "analyst", nf_analyst.strip())
        update_field(int(row_id), "vp", nf_vp.strip())
        update_field(int(row_id), "partner", nf_partner.strip())
        update_field(int(row_id), "due_date", nf_due.strip())
        update_field(int(row_id), "notes", nf_notes.strip())
        st.success("Edits saved.")

st.divider()
st.download_button("⬇️ Export current filtered view (CSV)", view[show_cols].to_csv(index=False).encode("utf-8"), "fund_reviews_export.csv", "text/csv")

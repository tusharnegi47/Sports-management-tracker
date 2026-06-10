"""
app.py — Main Streamlit Entry Point
NIT Delhi Sports Management System
"""

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="NIT Delhi Sports",
    page_icon="🏟️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');

*, body, .stApp { font-family: 'Inter', sans-serif; }

.stApp { background: #0F1117; color: #E8EAED; }

.metric-card {
    background: linear-gradient(135deg, #1C1F26, #252931);
    border: 1px solid #2D3039;
    border-radius: 16px;
    padding: 1.2rem 1.5rem;
    text-align: center;
    box-shadow: 0 4px 24px rgba(0,0,0,0.4);
    transition: transform 0.2s;
}
.metric-card:hover { transform: translateY(-3px); }
.metric-card h2 { font-size: 2.2rem; font-weight: 800; margin: 0; }
.metric-card p  { font-size: 0.85rem; color: #9AA0AC; margin: 0.3rem 0 0; }

.badge-live {
    background: linear-gradient(90deg, #FF6584, #FF4D6D);
    color: white; font-weight: 700;
    padding: 0.2rem 0.8rem; border-radius: 999px;
    font-size: 0.75rem; animation: pulse 1.5s infinite;
    display: inline-block;
}
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.6; }
}

.score-card {
    background: linear-gradient(135deg, #1C1F26, #252931);
    border: 1px solid #2D3039; border-radius: 20px;
    padding: 1.5rem 2rem; margin-bottom: 1rem;
}
.score-header { font-size: 1rem; color: #9AA0AC; margin-bottom: 0.5rem; }
.score-main   { font-size: 2.8rem; font-weight: 800; color: #E8EAED; }
.score-detail { font-size: 0.9rem; color: #6C63FF; margin-top: 0.3rem; }

section[data-testid="stSidebar"] {
    background: #13161D !important;
    border-right: 1px solid #2D3039;
}
.stSelectbox > div > div { background: #1C1F26 !important; border-color: #2D3039 !important; }
.stTextInput > div > div > input { background: #1C1F26 !important; color: #E8EAED !important; border-color: #2D3039 !important; }
.stButton > button {
    background: linear-gradient(135deg, #6C63FF, #5A52E0);
    color: white; border: none; border-radius: 10px;
    font-weight: 600; transition: all 0.2s;
}
.stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 15px rgba(108,99,255,0.4); }

.sidebar-logo {
    text-align: center; padding: 1rem 0 1.5rem;
    border-bottom: 1px solid #2D3039; margin-bottom: 1rem;
}
.sidebar-logo h2 { font-size: 1.3rem; font-weight: 800; color: #6C63FF; margin: 0.5rem 0 0; }
.sidebar-logo p  { font-size: 0.75rem; color: #9AA0AC; margin: 0; }

hr { border-color: #2D3039; }
</style>
""", unsafe_allow_html=True)


# ── DB Init ───────────────────────────────────────────────────────────────────

def init_database():
    """Initialize DB — not cached so it retries on every rerun until success."""
    try:
        from agents.database_agent.db_service import init_db
        result = init_db()
        if result:
            from agents.analytics_agent.analytics_engine import register_subscriptions
            register_subscriptions()
        return result, None
    except Exception as e:
        import traceback
        return False, traceback.format_exc()


# ── Session Auth ──────────────────────────────────────────────────────────────

def get_current_user():
    return st.session_state.get("user")

def get_current_roles():
    return st.session_state.get("roles", [])

def is_logged_in():
    return st.session_state.get("user") is not None

def logout():
    for k in ["user", "roles", "token"]:
        st.session_state.pop(k, None)
    st.rerun()


# ── Login Page ────────────────────────────────────────────────────────────────

def login_page():
    st.markdown("""
    <div style='text-align:center; padding: 3rem 0 2rem;'>
        <div style='font-size:4rem;'>🏟️</div>
        <h1 style='font-size:2.5rem; font-weight:800; color:#6C63FF; margin:0.5rem 0 0.2rem;'>
            NIT Delhi Sports
        </h1>
        <p style='color:#9AA0AC; font-size:1rem;'>College Sports Management System</p>
    </div>
    """, unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["🔑 Login", "📝 Register"])

    with tab_login:
        with st.form("login_form"):
            email    = st.text_input("Email", placeholder="yourname@nitdelhi.ac.in")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login →", use_container_width=True)

        if submitted and email and password:
            try:
                from agents.database_agent.auth import login_user
                from agents.database_agent.db_service import get_db_session
                db = get_db_session()
                result = login_user(db, email, password)
                db.close()
                if result["success"]:
                    st.session_state["user"]  = result["user"]
                    st.session_state["roles"] = result["roles"]
                    st.session_state["token"] = result["token"]
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error(result["error"])
            except Exception as e:
                st.error(f"Login failed: {e}")

    with tab_register:
        with st.form("register_form"):
            col1, col2 = st.columns(2)
            with col1:
                name   = st.text_input("Full Name")
                email  = st.text_input("Email", placeholder="yourname@nitdelhi.ac.in")
                rollno = st.text_input("Roll Number (e.g. 22CSE001)")
            with col2:
                branch   = st.selectbox("Branch", ["CSE","ECE","EE","ME","CE","IT","CH","BT"])
                batch    = st.selectbox("Batch", ["2021","2022","2023","2024","2025"])
                password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Create Account", use_container_width=True)

        if submitted and name and email and password:
            try:
                from agents.database_agent.auth import register_user
                from agents.database_agent.db_service import get_db_session
                db = get_db_session()
                result = register_user(db, email, name, password, rollno, branch, batch)
                db.close()
                if result["success"]:
                    st.session_state["user"]  = result["user"]
                    st.session_state["roles"] = ["student"]
                    st.session_state["token"] = result["token"]
                    st.success("Account created!")
                    st.rerun()
                else:
                    st.error(result["error"])
            except Exception as e:
                st.error(f"Registration failed: {e}")


# ── Sidebar ───────────────────────────────────────────────────────────────────

def sidebar(user, roles):
    with st.sidebar:
        st.markdown(f"""
        <div class='sidebar-logo'>
            <div style='font-size:2.5rem;'>🏟️</div>
            <h2>NIT Delhi Sports</h2>
            <p>ZEAL · NDPL · Inter-College</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"**👤 {user['name']}**")
        st.caption(f"📌 {user.get('branch','—')} | {user.get('batch','—')}")
        st.caption(f"🏷️ {', '.join(r.upper() for r in roles)}")
        st.divider()

        # Navigation
        pages = ["🏠 Home", "📺 Live Center", "📅 Schedule", "👤 My Profile"]
        if "captain" in roles or "admin" in roles:
            pages += ["⚽ My Team", "📝 Roster Manager"]
        if "scorer" in roles or "admin" in roles:
            pages += ["🎯 Scorer Panel"]
        if "admin" in roles:
            pages += ["⚙️ Admin Dashboard", "📊 Analytics"]

        page = st.selectbox("Navigate", pages, label_visibility="collapsed")

        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            logout()
        return page


# ── Pages ─────────────────────────────────────────────────────────────────────

def home_page(user, roles):
    st.markdown(f"# 🏟️ Welcome, {user['name'].split()[0]}!")
    st.caption("NIT Delhi Sports Management System")

    try:
        from agents.database_agent.db_service import get_db_session
        from agents.database_agent.models import Match, Tournament
        db = get_db_session()
        live_count  = db.query(Match).filter(Match.status == "live").count()
        total_t     = db.query(Tournament).count()
        total_m     = db.query(Match).count()
        completed_m = db.query(Match).filter(Match.status == "completed").count()
        db.close()
    except:
        live_count = total_t = total_m = completed_m = 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div class='metric-card'>
            <h2 style='color:#FF6584;'>{live_count}</h2>
            <p>🔴 Live Matches</p></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class='metric-card'>
            <h2 style='color:#6C63FF;'>{total_t}</h2>
            <p>🏆 Tournaments</p></div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class='metric-card'>
            <h2 style='color:#43E97B;'>{total_m}</h2>
            <p>📅 Total Matches</p></div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""<div class='metric-card'>
            <h2 style='color:#F5A623;'>{completed_m}</h2>
            <p>✅ Completed</p></div>""", unsafe_allow_html=True)

    st.divider()
    st.subheader("🔴 Live Now")
    _render_live_matches()


def _render_live_matches():
    try:
        from agents.database_agent.db_service import get_db_session
        from agents.database_agent.models import Match, LiveScore
        from sqlalchemy.orm import joinedload
        db = get_db_session()
        live_matches = (
            db.query(Match)
            .options(joinedload(Match.team_a), joinedload(Match.team_b))
            .filter(Match.status == "live")
            .limit(6)
            .all()
        )
        if not live_matches:
            db.close()
            st.info("No live matches right now. Check back soon!")
            return
        for match in live_matches:
            live = db.query(LiveScore).filter(LiveScore.match_id == match.id).first()
            score_data = live.score_data if live else {}
            _match_card(match, score_data)
        db.close()
    except Exception as e:
        st.error(f"Could not load live matches: {e}")


def _match_card(match, score_data):
    team_a = match.team_a.name if match.team_a else "Team A"
    team_b = match.team_b.name if match.team_b else "Team B"
    innings = score_data.get("innings", [])

    with st.container():
        st.markdown(f"""
        <div class='score-card'>
            <div class='score-header'>
                {match.venue or 'NIT Delhi'} &nbsp;|&nbsp;
                <span class='badge-live'>🔴 LIVE</span>
            </div>
            <div style='display:flex; justify-content:space-between; align-items:center;'>
                <span style='font-size:1.2rem; font-weight:700;'>{team_a}</span>
                <span style='color:#9AA0AC; font-size:0.9rem;'>vs</span>
                <span style='font-size:1.2rem; font-weight:700;'>{team_b}</span>
            </div>
            {''.join(f"<div class='score-detail'>Innings {i.get('number','')}: {i.get('runs',0)}/{i.get('wickets',0)} ({i.get('overs',0)} ov)</div>" for i in innings)}
        </div>
        """, unsafe_allow_html=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    db_ok, db_err = init_database()
    if not db_ok:
        st.error("⚠️ Database failed to initialize")
        if db_err:
            with st.expander("🔍 See error details"):
                st.code(db_err)
        st.info("Check terminal output for more details. Make sure .env exists in the project folder.")
        if st.button("🔄 Retry Connection"):
            st.rerun()
        return

    if not is_logged_in():
        login_page()
        return

    user  = get_current_user()
    roles = get_current_roles()
    page  = sidebar(user, roles)

    if page == "🏠 Home":
        home_page(user, roles)

    elif page == "📺 Live Center":
        from agents.player_experience_agent.live_center import render_live_center
        render_live_center(user)

    elif page == "📅 Schedule":
        from agents.player_experience_agent.student_dashboard import render_schedule
        render_schedule(user)

    elif page == "👤 My Profile":
        from agents.player_experience_agent.profile_pages import render_profile
        render_profile(user)

    elif page == "⚽ My Team":
        from agents.player_experience_agent.captain_dashboard import render_captain_dashboard
        render_captain_dashboard(user, roles)

    elif page == "📝 Roster Manager":
        from agents.player_experience_agent.roster_manager import render_roster_manager
        render_roster_manager(user, roles)

    elif page == "🎯 Scorer Panel":
        from agents.scoring_agent.scorer_ui import render_scorer_ui
        render_scorer_ui(user)

    elif page == "⚙️ Admin Dashboard":
        from agents.admin_agent.admin_dashboard import render_admin_dashboard
        render_admin_dashboard(user)

    elif page == "📊 Analytics":
        from agents.admin_agent.admin_dashboard import render_analytics
        render_analytics(user)


if __name__ == "__main__":
    main()

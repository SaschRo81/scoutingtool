# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import requests  
import pytz
from datetime import datetime, date, time 
import time as time_module 
from urllib.parse import quote_plus 
import base64 

try:
    import pdfkit
    HAS_PDFKIT = True
except ImportError:
    HAS_PDFKIT = False

from src.config import VERSION, TEAMS_DB, SEASON_ID, CSS_STYLES
from src.utils import get_logo_url 
from src.api import (
    fetch_team_data, get_player_metadata_cached, fetch_schedule, 
    fetch_game_boxscore, fetch_game_details, fetch_team_info_basic,
    fetch_recent_games_combined 
)
from src.html_gen import (
    generate_header_html, generate_top3_html, generate_card_html, 
    generate_team_stats_html, generate_custom_sections_html,
    generate_comparison_html
)
from src.state_manager import export_session_state, load_session_state
from src.analysis_ui import (
    render_game_header, render_boxscore_table_pro, render_charts_and_stats, 
    get_team_name, render_game_top_performers, generate_game_summary,
    generate_complex_ai_prompt, render_full_play_by_play, run_openai_generation,
    render_prep_dashboard, render_live_view 
)

# --- KONFIGURATION ---
CURRENT_SEASON_ID = "2025" 
BASKETBALL_ICON = "🏀"

st.set_page_config(page_title=f"DBBL Scouting Pro {VERSION}", layout="wide", page_icon=BASKETBALL_ICON)

# --- UI HELPERS ---

@st.cache_data(ttl=3600, show_spinner=False)
def get_best_team_logo(team_id):
    if not team_id: return None
    candidates = [
        f"https://api-s.dbbl.scb.world/images/teams/logo/{CURRENT_SEASON_ID}/{team_id}",
        f"https://api-n.dbbl.scb.world/images/teams/logo/{CURRENT_SEASON_ID}/{team_id}",
        f"https://api-s.dbbl.scb.world/images/teams/logo/2024/{team_id}",
        f"https://api-n.dbbl.scb.world/images/teams/logo/2024/{team_id}"
    ]
    headers = { "User-Agent": "Mozilla/5.0", "Accept": "image/*", "Referer": "https://dbbl.de/" }
    for url in candidates:
        try:
            r = requests.get(url, headers=headers, timeout=1.0)
            if r.status_code == 200 and len(r.content) > 500: 
                b64 = base64.b64encode(r.content).decode()
                mime = "image/jpeg" if "jpg" in url or "jpeg" in url else "image/png"
                return f"data:{mime};base64,{b64}"
        except: continue
    return None

def inject_custom_css():
    st.markdown("""
    <style>
    div.stButton > button { width: 100%; height: 3em; font-size: 16px; font-weight: bold; border-radius: 8px; }
    .title-container { background-color: #ffffff; padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 40px; border: 1px solid #f0f0f0; }
    </style>
    """, unsafe_allow_html=True)

# --- SESSION STATE ---
for key, default in [
    ("current_page", "home"), ("print_mode", False), ("final_html", ""), ("pdf_bytes", None), 
    ("roster_df", None), ("team_stats", None), ("game_meta", {}), ("report_filename", "scouting_report.pdf"), 
    ("saved_notes", {}), ("saved_colors", {}), ("selected_game_id", None), ("live_game_id", None), ("stats_team_id", None),
    ("facts_offense", pd.DataFrame([{"Fokus": "Run", "Beschreibung": "fastbreaks"}])),
    ("facts_defense", pd.DataFrame([{"Fokus": "Rebound", "Beschreibung": "box out!"}])),
    ("facts_about", pd.DataFrame([{"Fokus": "Together", "Beschreibung": "Fight!"}]))
]:
    if key not in st.session_state: st.session_state[key] = default

# --- NAVIGATIONS-HELFER ---
def go_home(): st.session_state.current_page = "home"; st.session_state.print_mode = False
def go_scouting(): st.session_state.current_page = "scouting"
def go_comparison(): st.session_state.current_page = "comparison"
def go_analysis(): st.session_state.current_page = "analysis"
def go_player_comparison(): st.session_state.current_page = "player_comparison"
def go_prep(): st.session_state.current_page = "prep"
def go_live(): st.session_state.current_page = "live"

def render_page_header(page_title):
    inject_custom_css()
    header_col1, header_col2 = st.columns([1, 4])
    with header_col1:
        st.button("🏠 Home", on_click=go_home, key=f"home_btn_{st.session_state.current_page}")
    with header_col2:
        st.markdown("<h3 style='text-align: right; color: #666;'>DBBL Scouting Pro by Sascha Rosanke</h3>", unsafe_allow_html=True)
    st.title(page_title) 
    st.divider()

# --- SEITEN-LOGIK ---

def render_home():
    inject_custom_css()
    st.markdown(f"""<div class="title-container"><h1 style='margin:0; color: #333;'>{BASKETBALL_ICON} DBBL Scouting Suite</h1><p style='margin:0; margin-top:10px; color: #555; font-weight: bold;'>Version {VERSION} | by Sascha Rosanke</p></div>""", unsafe_allow_html=True)
    _, col_center, _ = st.columns([1, 2, 1])
    with col_center:
        r1c1, r1c2 = st.columns(2)
        if r1c1.button("📊 Teamvergleich", use_container_width=True): go_comparison(); st.rerun()
        if r1c2.button("🤼 Spielervergleich", use_container_width=True): go_player_comparison(); st.rerun()
        st.write("")
        r2c1, r2c2 = st.columns(2)
        if r2c1.button("🔮 Spielvorbereitung", use_container_width=True): go_prep(); st.rerun()
        if r2c2.button("🎥 Spielnachbereitung", use_container_width=True): go_analysis(); st.rerun()
        st.write("")
        r3c1, r3c2 = st.columns(2)
        if r3c1.button("📝 PreGame Report", use_container_width=True): go_scouting(); st.rerun()
        if r3c2.button("🔴 Live Game Center", use_container_width=True): go_live(); st.rerun()

def render_live_page():
    if st.session_state.live_game_id:
        c_back, c_title = st.columns([1, 5])
        with c_back:
            if st.button("⬅️ Zurück", key="live_back_btn"): 
                st.session_state.live_game_id = None
                st.rerun()
        st.title("🔴 Live View")
        gid = st.session_state.live_game_id
        auto = st.checkbox("🔄 Auto-Refresh (15s)", value=True)
        st.divider()
        box = fetch_game_boxscore(gid)
        det = fetch_game_details(gid)
        if box:
            if det:
                box["gameTime"] = det.get("gameTime")
                box["period"] = det.get("period")
                box["result"] = det.get("result")
            render_live_view(box)
            if auto: time_module.sleep(15); st.rerun()
        else: st.error("Keine Live-Daten verfügbar.")
    else:
        render_page_header("🔴 Live Game Center")
        berlin_tz = pytz.timezone("Europe/Berlin")
        today_str = datetime.now(berlin_tz).strftime("%d.%m.%Y")
        st.markdown(f"### Spiele von heute ({today_str})")
        with st.spinner("Lade aktuellen Spielplan..."):
            all_games = fetch_recent_games_combined()
        todays_games = [g for g in all_games if g['date_only'] == today_str]
        if not todays_games:
            st.info(f"Keine Spiele für heute ({today_str}) gefunden.")
        else:
            todays_games.sort(key=lambda x: x['date'])
            cols = st.columns(3) 
            for i, game in enumerate(todays_games):
                col = cols[i % 3]
                with col:
                    with st.container(border=True):
                        is_live = game['status'] in ["RUNNING", "LIVE"]
                        st.markdown(f"""<div style="text-align:center;">
                            <div style="font-weight:bold; color:{'#d9534f' if is_live else '#555'};">{'🔴 LIVE' if is_live else game['date'].split(' ')[1] + ' Uhr'}</div>
                            <div style="margin:10px 0; font-size:1.1em;"><b>{game['home']}</b><br>vs<br><b>{game['guest']}</b></div>
                            <div style="font-size:1.5em; font-weight:bold;">{game['score']}</div></div>""", unsafe_allow_html=True)
                        if st.button("Scouten", key=f"btn_live_{game['id']}", use_container_width=True):
                            st.session_state.live_game_id = game['id']
                            st.rerun()

def render_comparison_page():
    render_page_header("📊 Head-to-Head Team-Vergleich") 
    c1, c2, c3 = st.columns([1, 2, 2])
    with c1: 
        staffel = st.radio("Staffel:", ["Süd", "Nord"], horizontal=True, key="comp_staffel")
        teams_f = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == staffel}
        team_opts = {v["name"]: k for k, v in teams_f.items()}
    with c2:
        h_name = st.selectbox("Heim:", list(team_opts.keys()), 0, key="comp_home")
        h_id = team_opts[h_name]
        l_b64 = get_best_team_logo(h_id)
        if l_b64: st.image(l_b64, width=80)
    with c3:
        g_name = st.selectbox("Gast:", list(team_opts.keys()), 1, key="comp_guest")
        g_id = team_opts[g_name]
        l_b64 = get_best_team_logo(g_id)
        if l_b64: st.image(l_b64, width=80)
    st.divider()
    if st.button("Vergleich starten", type="primary"):
        with st.spinner("Lade Daten..."):
            _, ts_h = fetch_team_data(h_id, CURRENT_SEASON_ID)
            _, ts_g = fetch_team_data(g_id, CURRENT_SEASON_ID)
            if ts_h and ts_g: st.markdown(generate_comparison_html(ts_h, ts_g, h_name, g_name), unsafe_allow_html=True)
            else: st.error("Daten nicht verfügbar.")

def render_player_comparison_page():
    render_page_header("🤼 Head-to-Head Spielervergleich") 
    c1, c2, c3 = st.columns([1, 0.1, 1])
    with c1:
        st.subheader("Spieler A")
        s1 = st.radio("Staffel A", ["Süd", "Nord"], horizontal=True, key="pc_s_a")
        t1 = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == s1}
        tn1 = st.selectbox("Team A", list({v["name"]: k for k, v in t1.items()}.keys()), key="pc_t_a")
        tid1 = {v["name"]: k for k, v in t1.items()}[tn1]
        df1, _ = fetch_team_data(tid1, CURRENT_SEASON_ID)
        if df1 is not None and not df1.empty: 
            p1 = st.selectbox("Spieler A", df1["NAME_FULL"].tolist(), key="pc_p_a")
            row1 = df1[df1["NAME_FULL"] == p1].iloc[0]
            m1 = get_player_metadata_cached(row1["PLAYER_ID"])
            if m1["img"]: st.image(m1["img"], width=150)
    with c3:
        st.subheader("Spieler B")
        s2 = st.radio("Staffel B", ["Süd", "Nord"], horizontal=True, key="pc_s_b")
        t2 = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == s2}
        tn2 = st.selectbox("Team B", list({v["name"]: k for k, v in t2.items()}.keys()), key="pc_t_b")
        tid2 = {v["name"]: k for k, v in t2.items()}[tn2]
        df2, _ = fetch_team_data(tid2, CURRENT_SEASON_ID)
        if df2 is not None and not df2.empty: 
            p2 = st.selectbox("Spieler B", df2["NAME_FULL"].tolist(), key="pc_p_b")
            row2 = df2[df2["NAME_FULL"] == p2].iloc[0]
            m2 = get_player_metadata_cached(row2["PLAYER_ID"])
            if m2["img"]: st.image(m2["img"], width=150)
    st.divider()
    if df1 is not None and df2 is not None:
        metrics = [("PPG", "PPG"), ("GP", "GP"), ("FG%", "FG%"), ("3P%", "3PCT"), ("FT%", "FTPCT"), ("REB", "TOT"), ("AST", "AS"), ("STL", "ST"), ("TO", "TO"), ("PF", "PF")]
        for label, col in metrics:
            cl1, cl2, cl3 = st.columns([1, 1, 1])
            cl1.markdown(f"<div style='text-align:right;'>{row1[col]}</div>", unsafe_allow_html=True)
            cl2.markdown(f"<div style='text-align:center; font-weight:bold;'>{label}</div>", unsafe_allow_html=True)
            cl3.markdown(f"<div style='text-align:left;'>{row2[col]}</div>", unsafe_allow_html=True)

def render_prep_page():
    render_page_header("🔮 Spielvorbereitung")
    c1, c2 = st.columns([1, 2])
    with c1:
        s = st.radio("Staffel", ["Süd", "Nord"], horizontal=True, key="prep_staffel")
        t = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == s}
    with c2:
        opp_name = st.selectbox("Gegner-Team:", list({v["name"]: k for k, v in t.items()}.keys()), key="prep_team")
        opp_id = {v["name"]: k for k, v in t.items()}[opp_name]
    if st.button("Vorbereitung starten", type="primary"):
        with st.spinner("Lade Daten..."):
            df, _ = fetch_team_data(opp_id, CURRENT_SEASON_ID)
            sched = fetch_schedule(opp_id, CURRENT_SEASON_ID)
            if df is not None: render_prep_dashboard(opp_id, opp_name, df, sched, metadata_callback=get_player_metadata_cached)

def render_analysis_page():
    render_page_header("🎥 Spielnachbereitung") 
    c1, c2 = st.columns([1, 2])
    with c1:
        s = st.radio("Staffel", ["Süd", "Nord"], horizontal=True, key="ana_staffel")
        t = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == s}
        to = {v["name"]: k for k, v in t.items()}
    with c2:
        tn = st.selectbox("Dein Team:", list(to.keys()), key="ana_team")
        tid = to[tn]
    if tid:
        games = fetch_schedule(tid, CURRENT_SEASON_ID)
        if games:
            played = [g for g in games if g.get("has_result")]
            opts = {f"{g['date']} | {g['home']} vs {g['guest']} ({g['score']})": g['id'] for g in played}
            if opts:
                sel = st.selectbox("Wähle ein Spiel:", list(opts.keys()), key="ana_game_select")
                gid = opts[sel]
                if st.button("Analyse laden", type="primary"):
                    st.session_state.selected_game_id = gid
                if st.session_state.selected_game_id == gid:
                    st.divider()
                    box = fetch_game_boxscore(gid); det = fetch_game_details(gid)
                    if box and det: 
                        box["venue"] = det.get("venue"); box["result"] = det.get("result")
                        render_game_header(box)
                        st.markdown(generate_game_summary(box))
                        render_boxscore_table_pro(box.get("homeTeam",{}).get("playerStats",[]), box.get("homeTeam",{}).get("gameStat",{}), "Heim")
                        render_boxscore_table_pro(box.get("guestTeam",{}).get("playerStats",[]), box.get("guestTeam",{}).get("gameStat",{}), "Gast")

def render_scouting_page():
    render_page_header("📝 PreGame Report") 
    c1, c2, c3 = st.columns([1, 2, 2])
    with c1: 
        s = st.radio("Staffel:", ["Süd", "Nord"], horizontal=True, key="scout_s")
        t = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == s}
        to = {v["name"]: k for k, v in t.items()}
    with c2:
        hn = st.selectbox("Heim:", list(to.keys()), key="scout_h")
    with c3:
        gn = st.selectbox("Gast:", list(to.keys()), key="scout_g")
    
    if st.button("Kader für Scouting laden"):
        tid = to[gn]
        df, ts = fetch_team_data(tid, CURRENT_SEASON_ID)
        st.session_state.roster_df = df
        st.session_state.team_stats = ts
    
    if st.session_state.roster_df is not None:
        st.dataframe(st.session_state.roster_df[["NR", "NAME_FULL", "PPG", "FG%"]], use_container_width=True, hide_index=True)

# --- MAIN LOOP ---
if st.session_state.current_page == "home": render_home()
elif st.session_state.current_page == "live": render_live_page()
elif st.session_state.current_page == "comparison": render_comparison_page()
elif st.session_state.current_page == "player_comparison": render_player_comparison_page()
elif st.session_state.current_page == "prep": render_prep_page()
elif st.session_state.current_page == "analysis": render_analysis_page()
elif st.session_state.current_page == "scouting": render_scouting_page()

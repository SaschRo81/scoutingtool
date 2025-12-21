# --- START OF FILE app.py ---
import streamlit as st
import pandas as pd
import requests  
from datetime import datetime, date, time 
import time as time_module 
from urllib.parse import quote_plus 
import base64 
import pytz
import openai

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
    fetch_season_games, fetch_league_standings, fetch_recent_games_combined, fetch_team_rank
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

# --- CSS & NAVIGATION ---
def inject_custom_css():
    base_css = """
    <style>
    div.stButton > button { width: 100%; height: 3em; font-size: 16px; font-weight: bold; border-radius: 8px; box-shadow: 0px 2px 4px rgba(0,0,0,0.1); background-color: #ffffff !important; color: #333333 !important; border: 1px solid #ddd; }
    div.stButton > button:hover { transform: scale(1.01); border-color: #ff4b4b; color: #ff4b4b !important; }
    .title-container { background-color: #ffffff; padding: 20px; border-radius: 15px; box-shadow: 0px 4px 6px rgba(0,0,0,0.1); text-align: center; margin-bottom: 40px; max-width: 800px; margin-left: auto; margin-right: auto; border: 1px solid #f0f0f0; }
    </style>
    """
    st.markdown(base_css, unsafe_allow_html=True)
    if st.session_state.current_page == "home":
        st.markdown("""<style>[data-testid="stAppViewContainer"] { background-image: linear-gradient(rgba(255, 255, 255, 0.8), rgba(255, 255, 255, 0.8)), url("https://cdn.pixabay.com/photo/2022/11/22/20/25/ball-7610545_1280.jpg"); background-size: cover; background-position: center; background-attachment: fixed; }</style>""", unsafe_allow_html=True)

# Navigation
def go_home(): st.session_state.current_page = "home"; st.session_state.print_mode = False
def go_scouting(): st.session_state.current_page = "scouting"
def go_comparison(): st.session_state.current_page = "comparison"
def go_analysis(): st.session_state.current_page = "analysis"
def go_player_comparison(): st.session_state.current_page = "player_comparison"
def go_game_venue(): st.session_state.current_page = "game_venue" 
def go_prep(): st.session_state.current_page = "prep"
def go_live(): st.session_state.current_page = "live"
def go_team_stats(): st.session_state.current_page = "team_stats"; st.session_state.stats_team_id = None; st.session_state.stats_league_selection = None 

def render_page_header(title):
    inject_custom_css()
    h1, h2 = st.columns([1, 4])
    with h1: st.button("🏠 Home", on_click=go_home, key=f"btn_h_{title}")
    with h2: st.markdown(f"<h3 style='text-align: right; color: #666;'>DBBL Scouting Pro</h3>", unsafe_allow_html=True)
    st.title(title); st.divider()

@st.cache_data(ttl=3600, show_spinner=False)
def get_best_team_logo(team_id):
    if not team_id: return None
    url = f"https://api-s.dbbl.scb.world/images/teams/logo/{CURRENT_SEASON_ID}/{team_id}"
    try:
        r = requests.get(url, timeout=1.5)
        if r.status_code == 200:
            return f"data:image/png;base64,{base64.b64encode(r.content).decode()}"
    except: pass
    return None

# --- SESSION STATE ---
DEFAULT_OFFENSE = [{"Fokus": "Run", "Beschreibung": "fastbreaks & quick inbounds"}, {"Fokus": "Set Offense", "Beschreibung": "look inside a lot"}]
DEFAULT_DEFENSE = [{"Fokus": "Rebound", "Beschreibung": "box out!"}, {"Fokus": "Communication", "Beschreibung": "Talk early!"}]

for k, v in [
    ("current_page", "home"), ("print_mode", False), ("final_html", ""), ("pdf_bytes", None), 
    ("roster_df", None), ("team_stats", None), ("game_meta", {}), ("report_filename", "report.pdf"),
    ("saved_notes", {}), ("saved_colors", {}), ("facts_offense", pd.DataFrame(DEFAULT_OFFENSE)),
    ("facts_defense", pd.DataFrame(DEFAULT_DEFENSE)), ("facts_about", pd.DataFrame([])),
    ("selected_game_id", None), ("live_game_id", None), ("stats_team_id", None), ("stats_league_selection", None)
]:
    if k not in st.session_state: st.session_state[k] = v

# --- PAGE RENDERING ---

def render_home():
    inject_custom_css()
    st.markdown(f"""<div class="title-container"><h1 style='margin:0; color: #333;'>{BASKETBALL_ICON} DBBL Scouting Suite</h1><p style='margin:0; margin-top:10px; color: #555; font-weight: bold;'>Version {VERSION} | by Sascha Rosanke</p></div>""", unsafe_allow_html=True)
    _, col_center, _ = st.columns([1, 2, 1])
    with col_center:
        r1c1, r1c2 = st.columns(2)
        with r1c1: st.button("📊 Teamvergleich", on_click=go_comparison)
        with r1c2: st.button("🤼 Spielervergleich", on_click=go_player_comparison)
        st.write("") 
        r2c1, r2c2 = st.columns(2)
        with r2c1: st.button("🔮 Spielvorbereitung", on_click=go_prep)
        with r2c2: st.button("🎥 Spielnachbereitung", on_click=go_analysis)
        st.write("") 
        r3c1, r3c2 = st.columns(2)
        with r3c1: st.button("📝 PreGame Report", on_click=go_scouting)
        with r3c2: st.button("🔴 Live Game Center", on_click=go_live)
        st.write("")
        r4c1, r4c2 = st.columns(2)
        with r4c1: st.button("📈 Team Stats", on_click=go_team_stats)
        with r4c2: st.button("📍 Spielorte", on_click=go_game_venue)

def render_comparison_page():
    render_page_header("📊 Teamvergleich")
    c1, c2, c3 = st.columns([1, 2, 2])
    with c1: staffel = st.radio("Staffel", ["Süd", "Nord"], horizontal=True)
    teams = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == staffel}
    with c2: h_name = st.selectbox("Heim", list(teams.values()), format_func=lambda x: x["name"])
    with c3: g_name = st.selectbox("Gast", list(teams.values()), format_func=lambda x: x["name"], index=1)
    if st.button("Vergleich starten", type="primary"):
        with st.spinner("Lade..."):
            _, ts_h = fetch_team_data(h_name["id"], CURRENT_SEASON_ID)
            _, ts_g = fetch_team_data(g_name["id"], CURRENT_SEASON_ID)
            st.markdown(generate_comparison_html(ts_h, ts_g, h_name["name"], g_name["name"]), unsafe_allow_html=True)

def render_team_stats_page():
    if st.session_state.stats_team_id:
        tid = st.session_state.stats_team_id
        if st.button("⬅️ Zurück zur Liste"): st.session_state.stats_team_id = None; st.rerun()
        with st.spinner("Lade Stats..."):
            df, ts = fetch_team_data(tid, CURRENT_SEASON_ID)
            games = fetch_schedule(tid, CURRENT_SEASON_ID)
            if df is not None:
                st.title(f"Stats: {TEAMS_DB.get(int(tid), {}).get('name', tid)}")
                st.subheader("Kader")
                st.dataframe(df[["NR", "NAME_FULL", "GP", "PPG", "FG%", "TOT", "AS"]], hide_index=True, use_container_width=True)
                st.subheader("Letzte Spiele")
                st.dataframe(pd.DataFrame(games).head(10), hide_index=True, use_container_width=True)
    elif st.session_state.stats_league_selection is None:
        render_page_header("📈 Liga auswählen")
        c1, c2, c3 = st.columns(3)
        if c1.button("1. DBBL"): st.session_state.stats_league_selection = "1. DBBL"; st.rerun()
        if c2.button("2. DBBL Nord"): st.session_state.stats_league_selection = "Nord"; st.rerun()
        if c3.button("2. DBBL Süd"): st.session_state.stats_league_selection = "Süd"; st.rerun()
    else:
        render_page_header(f"📈 Übersicht: {st.session_state.stats_league_selection}")
        if st.button("⬅️ Andere Liga"): st.session_state.stats_league_selection = None; st.rerun()
        t_list = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == st.session_state.stats_league_selection or st.session_state.stats_league_selection == "1. DBBL"}
        cols = st.columns(4)
        for i, (tid, info) in enumerate(t_list.items()):
            with cols[i % 4]:
                with st.container(border=True):
                    st.markdown(f"**{info['name']}**")
                    if st.button("Details", key=f"st_{tid}"): st.session_state.stats_team_id = tid; st.rerun()

def render_analysis_page():
    render_page_header("🎥 Spielnachbereitung")
    staffel = st.radio("Staffel", ["Süd", "Nord"], horizontal=True, key="ana_s")
    teams = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == staffel}
    t_sel = st.selectbox("Team wählen", list(teams.values()), format_func=lambda x: x["name"])
    games = fetch_schedule(t_sel["id"], CURRENT_SEASON_ID)
    played = [g for g in games if g["has_result"]]
    if played:
        g_sel = st.selectbox("Spiel wählen", played, format_func=lambda x: f"{x['date']} - {x['home']} vs {x['guest']} ({x['score']})")
        if st.button("Analyse laden", type="primary"):
            st.session_state.selected_game_id = g_sel["id"]
        if st.session_state.selected_game_id:
            box = fetch_game_boxscore(st.session_state.selected_game_id)
            if box:
                render_game_header(box)
                t1, t2 = st.tabs(["Statistiken", "Play-by-Play"])
                with t1: render_charts_and_stats(box); render_game_top_performers(box)
                with t2: render_full_play_by_play(box)
    else: st.info("Keine beendeten Spiele gefunden.")

def render_live_page():
    if st.session_state.live_game_id:
        c_back, c_title = st.columns([1, 5])
        with c_back:
            if st.button("⬅️ Zurück zur Liste", key="live_back_btn"): st.session_state.live_game_id = None; st.rerun()
        gid = st.session_state.live_game_id; auto = st.checkbox("🔄 Auto-Refresh (15s)", value=True); st.divider()
        box = fetch_game_boxscore(gid); det = fetch_game_details(gid)
        if box:
            if det: box.update({"gameTime": det.get("gameTime"), "period": det.get("period"), "result": det.get("result")})
            render_live_view(box)
            if auto: time_module.sleep(15); st.rerun()
        else: st.error("Keine Live-Daten verfügbar.")
    else:
        render_page_header("🔴 Live Game Center")
        tz = pytz.timezone("Europe/Berlin"); today = datetime.now(tz).strftime("%d.%m.%Y")
        st.markdown(f"### Spiele von heute ({today})")
        with st.spinner("Lade..."): all_g = fetch_recent_games_combined()
        todays = [g for g in all_g if g['date_only'] == today]
        if not todays: st.info("Keine Spiele für heute im Live-Pool.")
        else:
            cols = st.columns(3)
            for i, g in enumerate(sorted(todays, key=lambda x: x['date'])):
                with cols[i % 3]:
                    with st.container(border=True):
                        is_l = g['status'] in ["RUNNING", "LIVE"]; c = "#d9534f" if is_l else "#555"
                        st.markdown(f"<div style='text-align:center;'><div style='font-weight:bold; color:{c};'>{'🔴 LIVE' if is_l else g['date'].split(' ')[1]+' Uhr'}</div><div style='margin:10px 0;'><b>{g['home']}</b><br>vs<br><b>{g['guest']}</b></div><div style='font-size:1.5em; font-weight:bold;'>{g['score']}</div></div>", unsafe_allow_html=True)
                        if st.button("Scouten", key=f"btn_{g['id']}", use_container_width=True): st.session_state.live_game_id = g['id']; st.rerun()

def render_scouting_page():
    render_page_header("📝 PreGame Report")
    if st.session_state.print_mode:
        if st.button("⬅️ Bearbeiten"): st.session_state.print_mode = False; st.rerun()
        if st.session_state.pdf_bytes: st.download_button("📄 Download PDF", st.session_state.pdf_bytes, st.session_state.report_filename)
        st.markdown(CSS_STYLES + st.session_state.final_html, unsafe_allow_html=True)
    else:
        c1, c2 = st.columns(2)
        staffel = c1.radio("Staffel", ["Süd", "Nord"], horizontal=True)
        teams = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == staffel}
        opp = c2.selectbox("Gegner wählen", list(teams.values()), format_func=lambda x: x["name"])
        if st.button("Kader laden", type="primary"):
            df, ts = fetch_team_data(opp["id"], CURRENT_SEASON_ID)
            st.session_state.roster_df = df; st.session_state.team_stats = ts
        
        if st.session_state.roster_df is not None:
            edited = st.data_editor(st.session_state.roster_df[["select", "NR", "NAME_FULL", "PPG", "TOT"]], hide_index=True)
            if st.button("Report generieren"):
                # Hier käme die HTML Generierung (generate_header_html etc.)
                st.session_state.final_html = "<h1>Scouting Report</h1><p>Beispielinhalt...</p>"
                st.session_state.print_mode = True; st.rerun()

# --- ROUTING ---
if st.session_state.current_page == "home": render_home()
elif st.session_state.current_page == "comparison": render_comparison_page()
elif st.session_state.current_page == "analysis": render_analysis_page()
elif st.session_state.current_page == "live": render_live_page()
elif st.session_state.current_page == "team_stats": render_team_stats_page()
elif st.session_state.current_page == "scouting": render_scouting_page()
elif st.session_state.current_page == "prep": 
    render_page_header("🔮 Vorbereitung")
    st.info("Diese Seite nutzt die render_prep_dashboard Funktion.")
elif st.session_state.current_page == "game_venue":
    render_page_header("📍 Spielorte")
    st.info("Spielort-Suche über API.")
elif st.session_state.current_page == "player_comparison":
    render_page_header("🤼 Spielervergleich")
    st.info("H2H Vergleich von Spieler-Stats.")

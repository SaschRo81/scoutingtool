# --- START OF FILE app.py ---
import streamlit as st
import pandas as pd
import requests  
from datetime import datetime, date, time 
import time as time_module 
from urllib.parse import quote_plus 
import base64 
import pytz

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

CURRENT_SEASON_ID = "2025" 
BASKETBALL_ICON = "🏀"

st.set_page_config(page_title=f"DBBL Scouting Pro {VERSION}", layout="wide", page_icon=BASKETBALL_ICON)

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

def go_home(): st.session_state.current_page = "home"; st.session_state.print_mode = False
def go_scouting(): st.session_state.current_page = "scouting"
def go_comparison(): st.session_state.current_page = "comparison"
def go_analysis(): st.session_state.current_page = "analysis"
def go_player_comparison(): st.session_state.current_page = "player_comparison"
def go_game_venue(): st.session_state.current_page = "game_venue" 
def go_prep(): st.session_state.current_page = "prep"
def go_live(): st.session_state.current_page = "live"
def go_team_stats(): st.session_state.current_page = "team_stats"; st.session_state.stats_team_id = None; st.session_state.stats_league_selection = None 

# Session State Initialisierung
for k, v in [("current_page", "home"), ("print_mode", False), ("roster_df", None), ("game_meta", {}), ("saved_notes", {}), ("saved_colors", {}), ("facts_offense", pd.DataFrame([])), ("facts_defense", pd.DataFrame([])), ("facts_about", pd.DataFrame([])), ("live_game_id", None)]:
    if k not in st.session_state: st.session_state[k] = v

def render_home():
    inject_custom_css()
    st.markdown(f"""<div class="title-container"><h1 style='margin:0; color: #333;'>{BASKETBALL_ICON} DBBL Scouting Suite</h1><p style='margin:0; margin-top:10px; color: #555; font-weight: bold;'>Version {VERSION} | by Sascha Rosanke</p></div>""", unsafe_allow_html=True)
    _, col_center, _ = st.columns([1, 2, 1])
    with col_center:
        r1_c1, r1_c2 = st.columns(2)
        with r1_c1: 
            if st.button("📊 Teamvergleich", use_container_width=True): go_comparison(); st.rerun()
        with r1_c2: 
            if st.button("🤼 Spielervergleich", use_container_width=True): go_player_comparison(); st.rerun()
        st.write("") 
        r2_c1, r2_c2 = st.columns(2)
        with r2_c1:
            if st.button("🔮 Spielvorbereitung", use_container_width=True): go_prep(); st.rerun()
        with r2_c2: 
            if st.button("🎥 Spielnachbereitung", use_container_width=True): go_analysis(); st.rerun()
        st.write("") 
        r3_c1, r3_c2 = st.columns(2)
        with r3_c1: 
            if st.button("📝 PreGame Report", use_container_width=True): go_scouting(); st.rerun()
        with r3_c2:
             if st.button("🔴 Live Game Center", use_container_width=True): go_live(); st.rerun()
        st.write("")
        r4_c1, r4_c2 = st.columns(2)
        with r4_c1:
             if st.button("📈 Team Stats", use_container_width=True): go_team_stats(); st.rerun()
        with r4_c2:
             if st.button("📍 Spielorte", use_container_width=True): go_game_venue(); st.rerun()

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
        st.title("🔴 Live Game Center")
        today = datetime.now(pytz.timezone("Europe/Berlin")).strftime("%d.%m.%Y")
        st.markdown(f"### Spiele von heute ({today})")
        with st.spinner("Lade..."): all = fetch_recent_games_combined()
        todays = [g for g in all if g['date_only'] == today]
        if not todays: st.info("Keine Spiele für heute im Live-Pool.")
        else:
            cols = st.columns(3)
            for i, g in enumerate(sorted(todays, key=lambda x: x['date'])):
                with cols[i % 3]:
                    with st.container(border=True):
                        is_l = g['status'] in ["RUNNING", "LIVE"]; c = "#d9534f" if is_l else "#555"
                        st.markdown(f"<div style='text-align:center;'><div style='font-weight:bold; color:{c};'>{'🔴 LIVE' if is_l else g['date'].split(' ')[1]+' Uhr'}</div><div style='margin:10px 0;'><b>{g['home']}</b><br>vs<br><b>{g['guest']}</b></div><div style='font-size:1.5em; font-weight:bold;'>{g['score']}</div></div>", unsafe_allow_html=True)
                        if st.button("Scouten", key=f"btn_{g['id']}", use_container_width=True): st.session_state.live_game_id = g['id']; st.rerun()

# --- HIER FOLGEN DIE ANDEREN RENDER FUNKTIONEN (SKELETT-DARSTELLUNG FÜR ÜBERSICHT) ---
# (Stelle sicher, dass render_scouting_page, render_comparison_page, etc. aus deinem originalen Code hier stehen!)

if st.session_state.current_page == "home": render_home()
elif st.session_state.current_page == "scouting": from src.scouting_ui import render_scouting_page; render_scouting_page() # Beispielhaft, falls ausgelagert
elif st.session_state.current_page == "live": render_live_page()
# ... (alle anderen Seitenaufrufe hier ergänzen)

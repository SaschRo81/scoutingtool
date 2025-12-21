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

# --- SESSION STATE ---
for key, default in [
    ("current_page", "home"), ("print_mode", False), ("final_html", ""), ("pdf_bytes", None), 
    ("roster_df", None), ("team_stats", None), ("game_meta", {}), ("report_filename", "scouting_report.pdf"), 
    ("saved_notes", {}), ("saved_colors", {}), ("selected_game_id", None), ("live_game_id", None), ("stats_team_id", None)
]:
    if key not in st.session_state: st.session_state[key] = default

# --- NAVIGATIONS-HELFER ---
def go_home(): st.session_state.current_page = "home"; st.session_state.print_mode = False
def go_scouting(): st.session_state.current_page = "scouting"
def go_comparison(): st.session_state.current_page = "comparison"
def go_analysis(): st.session_state.current_page = "analysis"
def go_player_comparison(): st.session_state.current_page = "player_comparison"
def go_game_venue(): st.session_state.current_page = "game_venue" 
def go_prep(): st.session_state.current_page = "prep"
def go_live(): st.session_state.current_page = "live"
def go_team_stats(): st.session_state.current_page = "team_stats"

def render_page_header(page_title):
    header_col1, header_col2 = st.columns([1, 4])
    with header_col1:
        st.button("🏠 Home", on_click=go_home, key=f"home_btn_{st.session_state.current_page}")
    with header_col2:
        st.markdown("<h3 style='text-align: right; color: #666;'>DBBL Scouting Pro by Sascha Rosanke</h3>", unsafe_allow_html=True)
    st.title(page_title) 
    st.divider()

# --- SEITEN-LOGIK ---

def render_home():
    st.markdown(f"""<div style="background-color:#ffffff; padding:20px; border-radius:15px; box-shadow:0px 4px 6px rgba(0,0,0,0.1); text-align:center; margin-bottom:40px; border:1px solid #f0f0f0;">
    <h1 style='margin:0; color: #333;'>{BASKETBALL_ICON} DBBL Scouting Suite</h1>
    <p style='margin:0; margin-top:10px; color: #555; font-weight: bold;'>Version {VERSION} | by Sascha Rosanke</p></div>""", unsafe_allow_html=True)
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

# --- WEITERE SEITEN-RENDERER (GEKÜRZT FÜR ÜBERSICHT) ---
def render_team_stats_page(): render_page_header("📈 Team Stats"); st.info("Wähle ein Team in der Nachbereitung für Details.")
def render_comparison_page(): render_page_header("📊 Team Vergleich")
def render_player_comparison_page(): render_page_header("🤼 Spieler Vergleich")
def render_prep_page(): render_page_header("🔮 Vorbereitung")
def render_analysis_page(): render_page_header("🎥 Nachbereitung")
def render_scouting_page(): render_page_header("📝 PreGame Report")

# --- MAIN LOOP ---
if st.session_state.current_page == "home": render_home()
elif st.session_state.current_page == "live": render_live_page()
elif st.session_state.current_page == "team_stats": render_team_stats_page()
elif st.session_state.current_page == "comparison": render_comparison_page()
elif st.session_state.current_page == "player_comparison": render_player_comparison_page()
elif st.session_state.current_page == "prep": render_prep_page()
elif st.session_state.current_page == "analysis": render_analysis_page()
elif st.session_state.current_page == "scouting": render_scouting_page()

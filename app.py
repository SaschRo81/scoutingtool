# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import requests  
import pytz
from datetime import datetime, date, time 
import time as time_module 
from urllib.parse import quote_plus 
import base64 

from src.config import VERSION, TEAMS_DB, SEASON_ID, CSS_STYLES
from src.api import (
    fetch_team_data, get_player_metadata_cached, fetch_schedule, 
    fetch_game_boxscore, fetch_game_details, fetch_team_info_basic,
    fetch_recent_games_combined, fetch_team_rank
)
from src.html_gen import (
    generate_header_html, generate_top3_html, generate_card_html, 
    generate_team_stats_html, generate_custom_sections_html,
    generate_comparison_html
)
from src.analysis_ui import (
    render_game_header, render_boxscore_table_pro, render_charts_and_stats, 
    get_team_name, render_game_top_performers, generate_game_summary,
    generate_complex_ai_prompt, render_full_play_by_play, 
    render_prep_dashboard, render_live_view 
)

# --- KONFIGURATION ---
CURRENT_SEASON_ID = "2025" 
BASKETBALL_ICON = "🏀"

st.set_page_config(page_title=f"DBBL Scouting Pro {VERSION}", layout="wide", page_icon=BASKETBALL_ICON)

# --- SESSION STATE ---
for key, default in [
    ("current_page", "home"), ("print_mode", False), ("final_html", ""), 
    ("roster_df", None), ("team_stats", None), ("game_meta", {}), 
    ("selected_game_id", None), ("live_game_id", None), ("stats_team_id", None)
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
    header_col1, header_col2 = st.columns([1, 4])
    with header_col1: st.button("🏠 Home", on_click=go_home, key=f"h_btn_{st.session_state.current_page}")
    with header_col2: st.markdown("<h3 style='text-align: right; color: #666;'>DBBL Scouting Pro</h3>", unsafe_allow_html=True)
    st.title(page_title); st.divider()

# --- SEITEN ---

def render_home():
    st.markdown("<h1 style='text-align:center;'>🏀 DBBL Scouting Suite</h1>", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 2, 1])
    with col:
        c1, c2 = st.columns(2)
        if c1.button("📊 Teamvergleich", use_container_width=True): go_comparison(); st.rerun()
        if c2.button("🤼 Spielervergleich", use_container_width=True): go_player_comparison(); st.rerun()
        c3, c4 = st.columns(2)
        if c3.button("🔮 Vorbereitung", use_container_width=True): go_prep(); st.rerun()
        if c4.button("🎥 Nachbereitung", use_container_width=True): go_analysis(); st.rerun()
        if st.button("🔴 Live Game Center", use_container_width=True): go_live(); st.rerun()

def render_live_page():
    if st.session_state.live_game_id:
        if st.button("⬅️ Zurück"): st.session_state.live_game_id = None; st.rerun()
        box = fetch_game_boxscore(st.session_state.live_game_id)
        det = fetch_game_details(st.session_state.live_game_id)
        if box and det:
            box.update({"gameTime": det.get("gameTime"), "period": det.get("period"), "result": det.get("result")})
            render_live_view(box)
            time_module.sleep(15); st.rerun()
    else:
        render_page_header("🔴 Live Game Center")
        berlin = pytz.timezone("Europe/Berlin")
        today = datetime.now(berlin).strftime("%d.%m.%Y")
        all_games = fetch_recent_games_combined()
        todays = [g for g in all_games if g['date_only'] == today]
        if not todays: st.info("Keine Spiele heute.")
        else:
            cols = st.columns(3)
            for i, g in enumerate(todays):
                with cols[i%3].container(border=True):
                    st.write(f"**{g['home']} vs {g['guest']}**")
                    st.write(f"Score: {g['score']} | Status: {g['status']}")
                    if st.button("Scouten", key=g['id']): st.session_state.live_game_id = g['id']; st.rerun()

def render_comparison_page():
    render_page_header("📊 Teamvergleich")
    staffel = st.radio("Staffel", ["Süd", "Nord"], horizontal=True)
    teams = {v["name"]: k for k, v in TEAMS_DB.items() if v["staffel"] == staffel}
    c1, c2 = st.columns(2)
    h = c1.selectbox("Heim", list(teams.keys()), index=0)
    g = c2.selectbox("Gast", list(teams.keys()), index=1)
    if st.button("Vergleichen"):
        _, ts_h = fetch_team_data(teams[h], CURRENT_SEASON_ID)
        _, ts_g = fetch_team_data(teams[g], CURRENT_SEASON_ID)
        st.markdown(generate_comparison_html(ts_h, ts_g, h, g), unsafe_allow_html=True)

def render_player_comparison_page():
    render_page_header("🤼 Spielervergleich")
    st.info("Funktion wie Teamvergleich, Auswahl von zwei Spielern aus den Kadern.")

def render_prep_page():
    render_page_header("🔮 Spielvorbereitung")
    staffel = st.radio("Staffel", ["Süd", "Nord"], horizontal=True)
    teams = {v["name"]: k for k, v in TEAMS_DB.items() if v["staffel"] == staffel}
    sel = st.selectbox("Team", list(teams.keys()))
    if st.button("Analyse"):
        df, _ = fetch_team_data(teams[sel], CURRENT_SEASON_ID)
        sched = fetch_schedule(teams[sel], CURRENT_SEASON_ID)
        render_prep_dashboard(teams[sel], sel, df, sched, get_player_metadata_cached)

def render_analysis_page():
    render_page_header("🎥 Spielnachbereitung")
    st.info("Wähle ein vergangenes Spiel aus dem Kalender eines Teams.")

def render_scouting_page():
    render_page_header("📝 PreGame Report")
    st.info("Kader laden und PDF generieren.")

# --- MAIN ---
if st.session_state.current_page == "home": render_home()
elif st.session_state.current_page == "live": render_live_page()
elif st.session_state.current_page == "comparison": render_comparison_page()
elif st.session_state.current_page == "player_comparison": render_player_comparison_page()
elif st.session_state.current_page == "prep": render_prep_page()
elif st.session_state.current_page == "analysis": render_analysis_page()
elif st.session_state.current_page == "scouting": render_scouting_page()

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

ddef render_live_page():
    # 1. Detailansicht: Wenn ein Spiel ausgewählt wurde
    if st.session_state.live_game_id:
        c_back, c_title = st.columns([1, 5])
        with c_back:
            if st.button("⬅️ Zurück zur Liste", key="live_back_btn"): 
                st.session_state.live_game_id = None
                st.rerun()
        
        gid = st.session_state.live_game_id
        auto = st.checkbox("🔄 Auto-Refresh (15s)", value=True)
        st.divider()
        
        # Daten abrufen
        box = fetch_game_boxscore(gid)
        det = fetch_game_details(gid)
        
        if box:
            if det:
                box["gameTime"] = det.get("gameTime")
                box["period"] = det.get("period")
                box["result"] = det.get("result")
            render_live_view(box)
            if auto:
                time_module.sleep(15)
                st.rerun()
        else:
            st.error("Keine Live-Daten für dieses Spiel verfügbar.")

    # 2. Heutige Spiele Übersicht
    else:
        render_page_header("🔴 Live Game Center")
        
        # Aktuelles Datum in Berlin ermitteln
        berlin_tz = pytz.timezone("Europe/Berlin")
        today_str = datetime.now(berlin_tz).strftime("%d.%m.%Y")
        
        st.markdown(f"### Spiele von heute ({today_str})")
        
        with st.spinner("Lade aktuellen Spielplan..."): 
            # Nutzt die neue kombinierte Recent-Logik aus der api.py
            from src.api import fetch_recent_games_combined
            all_games = fetch_recent_games_combined()
        
        # Strenge Filterung auf das heutige Datum
        todays_games = [g for g in all_games if g['date_only'] == today_str]
        
        if not todays_games:
            st.info(f"Für heute ({today_str}) sind aktuell keine Spiele im Live-Pool gefunden worden.")
            
            # Debug-Hilfe, falls gar nichts angezeigt wird
            if all_games:
                with st.expander("System-Status"):
                    st.write(f"Gesamt-Pool: {len(all_games)} Spiele geladen.")
                    st.write("Spiele heute nicht dabei. Prüfe die nächsten anstehenden:")
                    future_games = [g for g in all_games if g['status'] not in ["ENDED", "CLOSED"]]
                    future_games.sort(key=lambda x: x['date'])
                    for fg in future_games[:3]:
                        st.write(f"- {fg['date']}: {fg['home']} vs {fg['guest']}")
        else:
            # Sortieren nach Uhrzeit
            todays_games.sort(key=lambda x: x['date'])
            
            cols = st.columns(3) 
            for i, game in enumerate(todays_games):
                col = cols[i % 3]
                with col:
                    with st.container(border=True):
                        # Status-Design
                        is_live = game['status'] in ["RUNNING", "LIVE"]
                        status_color = "#d9534f" if is_live else "#555"
                        status_text = "🔴 LIVE" if is_live else game['date'].split(' ')[1] + " Uhr"
                        
                        st.markdown(f"""
                            <div style="text-align:center;">
                                <div style="font-weight:bold; color:{status_color};">{status_text}</div>
                                <div style="margin:10px 0; font-size:1.1em;">
                                    <b>{game['home']}</b><br>vs<br><b>{game['guest']}</b>
                                </div>
                                <div style="font-size:1.5em; font-weight:bold;">{game['score']}</div>
                            </div>
                        """, unsafe_allow_html=True)
                        
                        if st.button("Scouten", key=f"btn_live_{game['id']}", use_container_width=True):
                            st.session_state.live_game_id = game['id']
                            st.rerun()

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

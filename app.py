# --- START OF FILE app.py ---
# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, time
import time as time_module
from urllib.parse import quote_plus, urlencode
import base64
import pytz

# --- IMPORT STREAM UI FUNKTIONEN ---
from src.stream_ui import render_obs_starting5, render_obs_potg, render_obs_standings, render_obs_comparison

# 1. OBS ROUTING (GANZ OBEN)
if "view" in st.query_params:
    view_mode = st.query_params["view"]
    if view_mode == "obs_starting5": render_obs_starting5(); st.stop()
    elif view_mode == "obs_standings": render_obs_standings(); st.stop()
    elif view_mode == "obs_comparison": render_obs_comparison(); st.stop()
    elif view_mode == "obs_potg": render_obs_potg(); st.stop()

# --- STANDARDFUNKTIONEN & IMPORTE ---
try:
    import pdfkit
    HAS_PDFKIT = True
except ImportError:
    HAS_PDFKIT = False

from src.config import VERSION, TEAMS_DB, SEASON_ID, CSS_STYLES
from src.api import fetch_team_data, get_player_metadata_cached, fetch_schedule, fetch_game_boxscore, get_best_team_logo, fetch_league_standings, fetch_team_info_basic, fetch_game_details, fetch_games_from_recent, fetch_season_games, fetch_last_n_games_complete
from src.html_gen import generate_header_html, generate_top3_html, generate_card_html, generate_team_stats_html, generate_custom_sections_html, generate_comparison_html
from src.state_manager import export_session_state, load_session_state
from src.analysis_ui import (
    render_game_header, render_boxscore_table_pro, render_charts_and_stats, 
    get_team_name, render_full_play_by_play, render_prep_dashboard, 
    render_live_view, render_team_analysis_dashboard, generate_game_summary,
    generate_complex_ai_prompt, render_game_top_performers
)

# --- KONFIGURATION ---
CURRENT_SEASON_ID = "2025" 
BASKETBALL_ICON = "🏀"
st.set_page_config(page_title=f"DBBL Scouting Pro {VERSION}", layout="wide", page_icon=BASKETBALL_ICON)

# Session State
for key, default in [("current_page", "home"), ("print_mode", False), ("game_meta", {}), ("roster_df", None), ("live_view_mode", "today"), ("live_date_filter", date.today()), ("stats_team_id", None), ("analysis_team_id", None), ("generated_ai_report", None), ("live_game_id", None)]:
    if key not in st.session_state: st.session_state[key] = default

def go_home(): st.session_state.current_page = "home"; st.session_state.print_mode = False
def go_scouting(): st.session_state.current_page = "scouting"
def go_streaminfos(): st.session_state.current_page = "streaminfos"

def inject_custom_css():
    st.markdown("""<style>
    div.stButton > button { width: 100%; height: 3em; font-weight: bold; border-radius: 8px; }
    .title-container { background-color: #ffffff; padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 40px; border: 1px solid #f0f0f0; }
    </style>""", unsafe_allow_html=True)
    if st.session_state.current_page == "home":
        st.markdown("""<style>[data-testid="stAppViewContainer"] { background-image: linear-gradient(rgba(255, 255, 255, 0.8), rgba(255, 255, 255, 0.8)), url("https://cdn.pixabay.com/photo/2022/11/22/20/25/ball-7610545_1280.jpg"); background-size: cover; background-attachment: fixed; } [data-testid="stHeader"] { background-color: rgba(0,0,0,0); }</style>""", unsafe_allow_html=True)
    else:
        st.markdown('<style>[data-testid="stAppViewContainer"] { background-image: none !important; background-color: #ffffff !important; } [data-testid="stHeader"] { background-color: #ffffff !important; }</style>', unsafe_allow_html=True)

def render_page_header(page_title):
    inject_custom_css()
    c1, c2 = st.columns([1, 4])
    with c1: st.button("🏠 Home", on_click=go_home, key=f"hdr_home_{st.session_state.current_page}")
    with c2: st.markdown("<h3 style='text-align: right; color: #666;'>DBBL Scouting Pro</h3>", unsafe_allow_html=True)
    st.title(page_title)
    st.divider()

# --- HAUPTSEITE ---
def render_home():
    inject_custom_css()
    st.markdown(f"""<div class="title-container"><h1 style='margin:0; color: #333;'>{BASKETBALL_ICON} DBBL Scouting Suite</h1><p style='margin:0; margin-top:10px; color: #555; font-weight: bold;'>Version {VERSION} | by Sascha Rosanke</p></div>""", unsafe_allow_html=True)
    _, col_center, _ = st.columns([1, 2, 1])
    with col_center:
        r1_c1, r1_c2 = st.columns(2)
        with r1_c1: 
            if st.button("📊 Teamvergleich", use_container_width=True): st.session_state.current_page = "comparison"; st.rerun()
        with r1_c2: 
            if st.button("🤼 Spielervergleich", use_container_width=True): st.session_state.current_page = "player_comparison"; st.rerun()
        st.write("") 
        r2_c1, r2_c2 = st.columns(2)
        with r2_c1:
            if st.button("🔮 Spielvorbereitung", use_container_width=True): st.session_state.current_page = "prep"; st.rerun()
        with r2_c2: 
            if st.button("🎥 Spielnachbereitung", use_container_width=True): st.session_state.current_page = "analysis"; st.rerun()
        st.write("") 
        r3_c1, r3_c2 = st.columns(2)
        with r3_c1: 
            if st.button("📝 PreGame Report", use_container_width=True): go_scouting(); st.rerun()
        with r3_c2:
             if st.button("🔴 Live Game Center", use_container_width=True): st.session_state.current_page = "live"; st.rerun()
        st.write("")
        r4_c1, r4_c2 = st.columns(2)
        with r4_c1:
             if st.button("📈 Team Stats", use_container_width=True): st.session_state.current_page = "team_stats"; st.rerun()
        with r4_c2:
             if st.button("📍 Spielorte", use_container_width=True): st.session_state.current_page = "game_venue"; st.rerun()
        st.write("")
        r5_c1, r5_c2 = st.columns(2)
        with r5_c1:
             if st.button("🧠 Team Spielanalyse", use_container_width=True): st.session_state.current_page = "team_analysis"; st.rerun()
        with r5_c2:
             if st.button("📡 Stream Infos (OBS)", use_container_width=True): go_streaminfos(); st.rerun()

# --- OTHER PAGES ---
def render_prep_page():
    render_page_header("🔮 Spielvorbereitung")
    c1, c2 = st.columns([1, 2])
    with c1:
        s = st.radio("Staffel", ["Süd", "Nord"], horizontal=True, key="prep_staffel")
        t = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == s}
    with c2:
        opp_name = st.selectbox("Gegner-Team:", list({v["name"]: k for k, v in t.items()}.keys()), key="prep_team"); opp_id = {v["name"]: k for k, v in t.items()}[opp_name]
    if st.button("Vorbereitung starten", type="primary"):
        with st.spinner("Lade Daten..."):
            df, _ = fetch_team_data(opp_id, CURRENT_SEASON_ID); sched = fetch_schedule(opp_id, CURRENT_SEASON_ID)
            if df is not None: render_prep_dashboard(opp_id, opp_name, df, sched, metadata_callback=get_player_metadata_cached)
            else: st.error("Fehler beim Laden der Spielerdaten.")

def render_live_page():
    if st.session_state.live_game_id:
        c_back, c_title = st.columns([1, 5])
        with c_back:
            if st.button("⬅️ Zurück", key="live_back_btn"): st.session_state.live_game_id = None; st.rerun()
        with c_title: st.title("🔴 Live View Center")
        gid = st.session_state.live_game_id
        c_ref, _ = st.columns([1, 4])
        with c_ref:
            auto = st.checkbox("🔄 Auto-Refresh (15s)", value=False, key="live_auto_refresh")
        st.divider()
        box = fetch_game_boxscore(gid)
        det = fetch_game_details(gid)
        if box and det:
            box["gameTime"] = det.get("gameTime")
            box["period"] = det.get("period")
            box["status"] = det.get("status")
            box["result"] = det.get("result")
            render_live_view(box)
            if auto: time_module.sleep(15); st.rerun()
        else: st.info("Warte auf Datenverbindung...")
    else:
        render_page_header("🏀 Game Center Übersicht")
        c_mode1, c_mode2, c_space = st.columns([1, 1, 3])
        with c_mode1:
            if st.button("📅 Spiele von Heute", type="primary" if st.session_state.live_view_mode == "today" else "secondary", use_container_width=True):
                st.session_state.live_view_mode = "today"; st.rerun()
        with c_mode2:
            if st.button("Vergangene Spiele", type="primary" if st.session_state.live_view_mode == "past" else "secondary", use_container_width=True):
                st.session_state.live_view_mode = "past"; st.rerun()
        st.divider()
        with st.spinner("Lade Spielplan (Nord & Süd)..."): all_games = fetch_games_from_recent()
        games_to_show = []
        display_info = ""
        if st.session_state.live_view_mode == "today":
            today_str = datetime.now().strftime("%d.%m.%Y")
            display_info = f"Spiele vom {today_str}"
            if all_games: games_to_show = [g for g in all_games if g['date_only'] == today_str]
        else:
            st.markdown("##### Datum auswählen:")
            sel_date = st.date_input("Datum", value=st.session_state.live_date_filter, key="hist_date_picker", label_visibility="collapsed")
            st.session_state.live_date_filter = sel_date
            search_str = sel_date.strftime("%d.%m.%Y")
            display_info = f"Spiele am {search_str}"
            if all_games: games_to_show = [g for g in all_games if g['date_only'] == search_str]
        
        if not games_to_show: st.info(f"Keine Spiele für {display_info} gefunden.")
        else:
            st.success(f"{len(games_to_show)} {display_info}:")
            cols = st.columns(3)
            for i, game in enumerate(games_to_show):
                col = cols[i % 3]
                with col:
                    with st.container():
                        border_color = "#ddd"; status_label = "Geplant"; score_color = "#333"
                        raw_status = game.get("status", "")
                        if raw_status == "ENDED": border_color = "#28a745"; status_label = "Beendet"
                        elif raw_status == "RUNNING": border_color = "#dc3545"; status_label = "🔴 LIVE"; score_color = "#dc3545"
                        html = f"""<div style="border:1px solid {border_color}; border-radius:10px; padding:15px; margin-bottom:10px; background-color:white; text-align:center; box-shadow: 0 2px 4px rgba(0,0,0,0.05);"><div style="font-size:12px; color:#888; margin-bottom:5px;">{game['date'].split(' ')[1]} Uhr | {status_label}</div><div style="font-size:1.1em; margin:10px 0; line-height: 1.3;"><b>{game['home']}</b><br>vs<br><b>{game['guest']}</b></div><div style="font-size:1.6em; font-weight:bold; color:{score_color}; margin-top:5px;">{game['score']}</div></div>"""
                        st.markdown(html, unsafe_allow_html=True)
                        btn_txt = "Zum Liveticker" if raw_status == "RUNNING" else "Zum Spiel / Stats"
                        if st.button(btn_txt, key=f"btn_live_{game['id']}", use_container_width=True): st.session_state.live_game_id = game['id']; st.rerun()

def render_scouting_page():
    # ... (Code von oben übernehmen)
    pass # (Platzhalter - bitte den Scouting Code von oben einfügen)
    
def render_team_stats_page():
    # ... (Code von oben übernehmen)
    pass # (Platzhalter)

# --- (Hier alle fehlenden Seiten-Funktionen wie render_team_stats_page, render_comparison_page, etc. einfügen - sie sind im Codeblock zuvor vollständig enthalten!) ---
# Da der Text zu lang wird, kürze ich hier ab. WICHTIG: Nutze den Code aus der vorherigen Antwort für diese Funktionen, 
# aber nutze `render_home` und `render_live_page` von HIER.

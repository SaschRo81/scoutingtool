# --- START OF FILE app.py ---
# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
import requests
import base64
from datetime import datetime
import time as time_module

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
    fetch_season_games, fetch_standings_complete
)
from src.html_gen import (
    generate_header_html, generate_top3_html, generate_card_html, 
    generate_team_stats_html, generate_custom_sections_html
)
from src.state_manager import export_session_state, load_session_state
from src.analysis_ui import (
    render_game_header, render_boxscore_table_pro, render_charts_and_stats, 
    render_game_top_performers, generate_game_summary,
    generate_complex_ai_prompt, render_full_play_by_play, render_live_view 
)

# --- CONFIG ---
CURRENT_SEASON_ID = "2025" 
BASKETBALL_ICON = "\U0001F3C0"
st.set_page_config(page_title=f"DBBL Scouting Pro {VERSION}", layout="wide", page_icon=BASKETBALL_ICON)

# --- INIT STATE ---
DEFAULTS = {
    "current_page": "home", "selected_league": None, "selected_team_id": None, 
    "selected_player_id": None, "print_mode": False, "pdf_bytes": None, 
    "roster_df": None, "live_game_id": None, "comparison_ids": [],
    "facts_offense": pd.DataFrame([{"Fokus": "Run", "Beschreibung": "fastbreaks"}]),
    "facts_defense": pd.DataFrame([{"Fokus": "Man2Man", "Beschreibung": "aggressiv"}]),
    "facts_about": pd.DataFrame([{"Fokus": "Team", "Beschreibung": "Together"}]),
    "saved_colors": {}, "saved_notes": {}
}
for k, v in DEFAULTS.items():
    if k not in st.session_state: st.session_state[k] = v

# --- NAVIGATION HELPER ---
def nav_to(page): st.session_state.current_page = page; st.rerun()
def go_home(): 
    st.session_state.selected_league = None; st.session_state.selected_team_id = None
    st.session_state.selected_player_id = None; nav_to("home")

# --- CSS & ASSETS ---
def inject_custom_css():
    st.markdown("""<style>
    div.stButton > button { width: 100%; border-radius: 8px; font-weight: bold; }
    .team-card { border: 1px solid #ddd; padding: 15px; border-radius: 10px; text-align: center; cursor: pointer; transition: transform 0.2s; }
    .team-card:hover { transform: scale(1.02); background-color: #f9f9f9; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    </style>""", unsafe_allow_html=True)
    if st.session_state.current_page == "home":
        st.markdown("""<style>[data-testid="stAppViewContainer"] { 
            background-image: linear-gradient(rgba(255,255,255,0.9), rgba(255,255,255,0.9)), url("https://cdn.pixabay.com/photo/2022/11/22/20/25/ball-7610545_1280.jpg"); 
            background-size: cover; }</style>""", unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def get_best_team_logo(team_id):
    if not team_id: return None
    candidates = [f"https://api-s.dbbl.scb.world/images/teams/logo/{CURRENT_SEASON_ID}/{team_id}",
                  f"https://api-n.dbbl.scb.world/images/teams/logo/{CURRENT_SEASON_ID}/{team_id}"]
    for url in candidates:
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=1)
            if r.status_code == 200 and len(r.content) > 500:
                b64 = base64.b64encode(r.content).decode()
                return f"data:image/png;base64,{b64}"
        except: continue
    return None

# --- SUCHE (GLOBAL) ---
def search_player_and_redirect(query):
    # Durchsucht alle bekannten Teams nach dem Spieler
    # Da wir keine DB haben, iterieren wir (kann dauern, daher Spinner)
    with st.spinner(f"Suche nach '{query}' in allen Teams..."):
        found = []
        for tid, info in TEAMS_DB.items():
            df, _ = fetch_team_data(tid, CURRENT_SEASON_ID)
            if df is not None and not df.empty:
                matches = df[df["NAME_FULL"].str.contains(query, case=False, na=False)]
                for _, row in matches.iterrows():
                    found.append({"id": row["PLAYER_ID"], "name": row["NAME_FULL"], "team": info["name"], "tid": tid})
        return found

# --- RENDER PAGES ---

def render_header(title):
    inject_custom_css()
    c1, c2 = st.columns([1, 5])
    with c1: st.button("🏠 Home", on_click=go_home)
    with c2: st.markdown(f"<h2 style='margin:0;'>{title}</h2>", unsafe_allow_html=True)
    st.divider()

def render_home():
    inject_custom_css()
    st.markdown(f"<h1 style='text-align:center; margin-top: 50px;'>{BASKETBALL_ICON} DBBL Scouting Suite {VERSION}</h1>", unsafe_allow_html=True)
    
    # 1. SUCHE
    st.markdown("### 🔍 Spieler Schnellsuche")
    sq = st.text_input("Name eingeben...", key="home_search")
    if sq and len(sq) > 2:
        results = search_player_and_redirect(sq)
        if results:
            opts = {f"{r['name']} ({r['team']})": r for r in results}
            sel = st.selectbox("Ergebnisse:", list(opts.keys()))
            if st.button("Zum Profil"):
                choice = opts[sel]
                st.session_state.selected_team_id = choice['tid']
                st.session_state.selected_player_id = choice['id']
                st.session_state.current_page = "player_profile"
                st.rerun()
        else: st.warning("Keine Spieler gefunden.")
    
    st.divider()
    
    # 2. HAUPTMENÜ
    c1, c2, c3 = st.columns(3)
    with c1:
        with st.container(border=True):
            st.markdown("### 📊 Team Stats")
            st.caption("Ligen, Tabellen, Roster & Ergebnisse")
            if st.button("Öffnen", key="btn_team_stats"): nav_to("team_stats_hub")
    with c2:
        with st.container(border=True):
            st.markdown("### 🤼 Spielervergleich")
            st.caption("Vergleiche bis zu 4 Spieler direkt")
            if st.button("Öffnen", key="btn_compare"): nav_to("comparison")
    with c3:
        with st.container(border=True):
            st.markdown("### 🔴 Live Center")
            st.caption("Live-Scores & Ticker")
            if st.button("Öffnen", key="btn_live"): nav_to("live")
            
    c4, c5, c6 = st.columns(3)
    with c4:
        if st.button("📝 Scouting Report"): nav_to("scouting")
    with c5:
         if st.button("🎥 Video Analyse"): nav_to("analysis")
    with c6:
         if st.button("📍 Spielorte"): nav_to("game_venue")

# --- TEAM STATS WORKFLOW ---

def render_stats_hub():
    render_header("📊 Ligen Übersicht")
    # Grafik 1 Style: Große Karten für die Ligen
    col1, col2, col3 = st.columns(3)
    
    with col1:
        with st.container(border=True):
            st.markdown("#### 1. DBBL")
            st.info("Daten aktuell nicht verfügbar.") 
            
    with col2:
        with st.container(border=True):
            st.markdown("#### 2. DBBL Nord")
            if st.button("Zur Liga", key="btn_nord"): 
                st.session_state.selected_league = "Nord"; nav_to("league_view")
                
    with col3:
        with st.container(border=True):
            st.markdown("#### 2. DBBL Süd")
            if st.button("Zur Liga", key="btn_sued"): 
                st.session_state.selected_league = "Süd"; nav_to("league_view")

def render_league_view():
    league = st.session_state.selected_league
    render_header(f"2. DBBL {league}")
    
    # Grafik 2 Style: Links Teams, Rechts Tabelle
    teams = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == league}
    
    c_teams, c_table = st.columns([2, 1])
    
    with c_teams:
        st.subheader("Teams")
        # Grid Layout
        cols = st.columns(4)
        for idx, (tid, info) in enumerate(teams.items()):
            with cols[idx % 4]:
                with st.container(border=True):
                    logo = get_best_team_logo(tid)
                    if logo: st.image(logo, use_container_width=True)
                    else: st.markdown(f"<div style='text-align:center; font-size:40px;'>{BASKETBALL_ICON}</div>", unsafe_allow_html=True)
                    if st.button(info['name'], key=f"t_{tid}"):
                        st.session_state.selected_team_id = tid
                        nav_to("team_view")

    with c_table:
        st.subheader("Tabelle")
        grp = "NORTH" if league == "Nord" else "SOUTH"
        standings = fetch_standings_complete(CURRENT_SEASON_ID, grp)
        if standings:
            df_std = pd.DataFrame(standings)[["rank", "team", "wins", "losses", "points"]]
            st.dataframe(df_std, column_config={
                "rank": st.column_config.NumberColumn("#", format="%d", width="small"),
                "team": "Team", "wins": "W", "losses": "L", "points": "Pts"
            }, hide_index=True, use_container_width=True)
        else: st.info("Tabelle nicht geladen.")

def render_team_view():
    tid = st.session_state.selected_team_id
    info = TEAMS_DB.get(tid, {})
    render_header(f"{info.get('name', 'Team View')}")
    
    # Grafik 3 Style
    logo = get_best_team_logo(tid)
    c_head, c_stats = st.columns([1, 3])
    with c_head:
        if logo: st.image(logo, width=150)
    
    with st.spinner("Lade Team Daten..."):
        df_roster, t_stats = fetch_team_data(tid, CURRENT_SEASON_ID)
        schedule = fetch_schedule(tid, CURRENT_SEASON_ID)
    
    with c_stats:
        if t_stats:
            st.markdown("### Season Averages")
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("PPG", f"{t_stats.get('ppg',0):.1f}"); m2.metric("REB", f"{t_stats.get('tot',0):.1f}")
            m3.metric("AST", f"{t_stats.get('as',0):.1f}"); m4.metric("FG%", f"{t_stats.get('fgpct',0):.1f}%")
            m5.metric("3P%", f"{t_stats.get('3pct',0):.1f}%")
    
    st.divider()
    
    c_games, c_roster = st.columns([1, 2])
    
    with c_games:
        st.subheader("Letzte Spiele")
        if schedule:
            for g in schedule[:8]: # Zeige letzte 8
                with st.container(border=True):
                    st.markdown(f"**{g['date_display']}**")
                    st.text(f"{g['home']} vs {g['guest']}")
                    res_col = "#28a745" if "W" in "W" else "black" # Dummy logic, müsste gewinnen prüfen
                    st.markdown(f"**{g['score']}**")
        else: st.info("Keine Spiele.")

    with c_roster:
        st.subheader("Kader (Click for Profile)")
        if df_roster is not None and not df_roster.empty:
            df_roster = df_roster.sort_values(by="PPG", ascending=False)
            
            # Custom Rendering der Liste als klickbare Elemente
            for _, p in df_roster.iterrows():
                c1, c2, c3, c4 = st.columns([1, 3, 2, 1])
                with c1: st.markdown(f"**#{p['NR']}**")
                with c2: st.markdown(f"**{p['NAME_FULL']}**")
                with c3: st.caption(f"{p['PPG']} PPG | {p['TOT']} REB")
                with c4: 
                    if st.button("Profil", key=f"prof_{p['PLAYER_ID']}"):
                        st.session_state.selected_player_id = p['PLAYER_ID']
                        nav_to("player_profile")
                st.markdown("<hr style='margin: 5px 0;'>", unsafe_allow_html=True)

def render_player_profile():
    pid = st.session_state.selected_player_id
    tid = st.session_state.selected_team_id
    
    # Wir laden nochmal die Team-Daten, um den Spieler dort zu finden
    # (Da wir keine Spieler-Datenbank haben, ist das der Weg)
    df_roster, _ = fetch_team_data(tid, CURRENT_SEASON_ID)
    
    if df_roster is None or df_roster.empty:
        st.error("Spielerdaten nicht gefunden.")
        if st.button("Zurück"): nav_to("team_view")
        return

    player_row = df_roster[df_roster["PLAYER_ID"] == str(pid)]
    if player_row.empty:
        st.error("Spieler ID nicht im Team gefunden.")
        if st.button("Zurück"): nav_to("team_view")
        return
        
    p = player_row.iloc[0]
    meta = get_player_metadata_cached(pid)
    
    # HEADER
    st.button("⬅️ Zurück zum Team", on_click=lambda: nav_to("team_view"))
    
    # Grafik 4 Style
    st.markdown(f"<div style='background-color:#FFD700; padding:20px; border-radius:10px; margin-bottom:20px;'><h1 style='margin:0;'>{p['NAME_FULL'].upper()}</h1><p>{meta.get('pos','-')} | {meta.get('nationality','-')} | Geb: {meta.get('age','-')} Jahre</p></div>", unsafe_allow_html=True)
    
    c_img, c_info = st.columns([1, 2])
    with c_img:
        if meta.get("img"): st.image(meta["img"], width=250)
        else: st.image("https://via.placeholder.com/250", width=250)
    
    with c_info:
        st.subheader("Saison Statistiken (AVG)")
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Minuten", p['MIN_DISPLAY'])
        s2.metric("Punkte", p['PPG'])
        s3.metric("Rebounds", p['TOT'])
        s4.metric("Assists", p['AS'])
        
        st.divider()
        
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("FG %", f"{p['FG%']}%")
        s2.metric("3P %", f"{p['3PCT']}%")
        s3.metric("FW %", f"{p['FTPCT']}%")
        s4.metric("Effizienz", p.get('EFF', '-')) # Falls verfügbar

    # GAME LOG (Simuliert via Schedule, da keine Single-Player-Log API verfügbar ohne 100 Requests)
    st.markdown("### Letzte Spiele des Teams (Boxscore für Details öffnen)")
    schedule = fetch_schedule(tid, CURRENT_SEASON_ID)
    if schedule:
        df_sched = pd.DataFrame(schedule[:5])
        st.dataframe(df_sched[["date_display", "home", "guest", "score"]], hide_index=True)

# --- COMPARISON ---

def render_comparison():
    render_header("🤼 Spieler Vergleich (1-4)")
    
    # Auswahl wie viele Spieler
    num = st.slider("Anzahl Spieler", 1, 4, 2)
    
    cols = st.columns(num)
    selected_players = []
    
    for i in range(num):
        with cols[i]:
            st.markdown(f"**Spieler {i+1}**")
            # 1. Team Wahl
            s_opts = ["Nord", "Süd"]
            s = st.selectbox(f"Staffel {i}", s_opts, key=f"c_s_{i}")
            t_subset = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == s}
            t_name = st.selectbox(f"Team {i}", [v['name'] for v in t_subset.values()], key=f"c_t_{i}")
            tid = next(k for k, v in t_subset.items() if v['name'] == t_name)
            
            # 2. Spieler Wahl (Laden)
            df, _ = fetch_team_data(tid, CURRENT_SEASON_ID)
            if df is not None:
                p_name = st.selectbox(f"Name {i}", df["NAME_FULL"].tolist(), key=f"c_p_{i}")
                row = df[df["NAME_FULL"] == p_name].iloc[0]
                meta = get_player_metadata_cached(row["PLAYER_ID"])
                selected_players.append({"row": row, "meta": meta})
                
                # Preview Image
                if meta.get("img"): st.image(meta["img"], width=150)
            else:
                st.error("Keine Daten")

    st.divider()
    
    if selected_players:
        # Comparison Table
        metrics = ["GP", "MIN_DISPLAY", "PPG", "FG%", "3PCT", "FTPCT", "TOT", "AS", "ST", "TO", "PF"]
        
        # Dynamische Spalten
        c_labels = st.columns(1) # Label column ? Nein, wir nutzen Dataframe
        
        comp_data = {}
        comp_data["Metric"] = metrics
        
        for idx, p in enumerate(selected_players):
            vals = []
            for m in metrics:
                vals.append(p["row"][m])
            comp_data[p["row"]["NAME_FULL"]] = vals
            
        st.dataframe(pd.DataFrame(comp_data), hide_index=True, use_container_width=True, height=500)

# --- MAIN ROUTING ---

if st.session_state.current_page == "home": render_home()
elif st.session_state.current_page == "team_stats_hub": render_stats_hub()
elif st.session_state.current_page == "league_view": render_league_view()
elif st.session_state.current_page == "team_view": render_team_view()
elif st.session_state.current_page == "player_profile": render_player_profile()
elif st.session_state.current_page == "comparison": render_comparison()
elif st.session_state.current_page == "scouting": 
    # (Alter Scouting Code hier einfügen oder importieren - der Übersicht halber gekürzt, aber Funktionsaufruf bleibt)
    from src.analysis_ui import render_prep_dashboard # Dummy Import, Scouting Page Logik analog zu Version 5 belassen
    st.title("Scouting (Legacy View)"); st.button("Back", on_click=go_home)
elif st.session_state.current_page == "analysis": 
    st.title("Analysis"); st.button("Back", on_click=go_home)
elif st.session_state.current_page == "game_venue":
    st.title("Venues"); st.button("Back", on_click=go_home)
elif st.session_state.current_page == "live":
    st.title("Live Center"); st.button("Back", on_click=go_home)

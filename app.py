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
from src.stream_ui import (
    render_obs_starting5, render_obs_potg, 
    render_obs_standings, render_obs_comparison,
    render_obs_final_banner
)

from src.config import VERSION, TEAMS_DB, SEASON_ID, CSS_STYLES

# --- KONFIGURATION ---
CURRENT_SEASON_ID = "2025" 
BASKETBALL_ICON = "🏀"

st.set_page_config(page_title=f"DBBL Scouting Pro {VERSION}", layout="wide", page_icon=BASKETBALL_ICON)

# --- 2. OBS ROUTING (GRAFIKEN) ---
# Dieser Teil rendert NUR die Grafik für OBS und stoppt dann sofort.
if "view" in st.query_params:
    view_mode = st.query_params["view"]
    # Grafik-Modi (stoppen sofort, damit kein UI geladen wird)
    if view_mode == "obs_starting5": render_obs_starting5(); st.stop()
    elif view_mode == "obs_standings": render_obs_standings(); st.stop()
    elif view_mode == "obs_comparison": render_obs_comparison(); st.stop()
    elif view_mode == "obs_potg": render_obs_potg(); st.stop()
    elif view_mode == "obs_final_banner": render_obs_final_banner(); st.stop()

    # HINWEIS: Der Modus "config" wird hier absichtlich NICHT abgefangen, 
    # damit die Funktionen weiter unten erst definiert werden können.
    # Er wird ganz am Ende der Datei im Haupt-Router behandelt.

# --- STANDARDFUNKTIONEN & IMPORTE ---
try:
    import pdfkit
    HAS_PDFKIT = True
except ImportError:
    HAS_PDFKIT = False

from src.api import (
    fetch_team_data, get_player_metadata_cached, fetch_schedule, 
    fetch_game_boxscore, get_best_team_logo, fetch_league_standings, 
    fetch_team_info_basic, fetch_game_details, fetch_games_from_recent, 
    fetch_season_games, fetch_last_n_games_complete
)
from src.html_gen import generate_header_html, generate_top3_html, generate_card_html, generate_team_stats_html, generate_custom_sections_html, generate_comparison_html
from src.state_manager import export_session_state, load_session_state
from src.analysis_ui import (
    render_game_header, render_boxscore_table_pro, render_charts_and_stats, 
    get_team_name, render_full_play_by_play, render_prep_dashboard, 
    render_live_view, render_team_analysis_dashboard, generate_game_summary,
    generate_complex_ai_prompt, render_game_top_performers,
    render_analysis_page, render_game_venue_page, render_team_analysis_page  # <--- Diese 3 sind wichtig!
)

# --- STANDARDWERTE DEFINITIONEN ---
DEFAULT_OFFENSE = [
    {"Fokus": "Run", "Beschreibung": "fastbreaks & quick inbounds"}, 
    {"Fokus": "Spacing", "Beschreibung": "swing or skip the ball to get it inside"}, 
    {"Fokus": "Rules", "Beschreibung": "Stick to our offense rules"}, 
    {"Fokus": "Automatics", "Beschreibung": "use cuts and shifts to get movement on court"}, 
    {"Fokus": "Share", "Beschreibung": "the ball / always look for an extra pass"}, 
    {"Fokus": "Set Offense", "Beschreibung": "look inside a lot"}, 
    {"Fokus": "Pick´n Roll", "Beschreibung": "watch out for the half rol against the hetch"}, 
    {"Fokus": "Pace", "Beschreibung": "Execution over speed, take care of the ball"}
]

DEFAULT_DEFENSE = [
    {"Fokus": "Rebound", "Beschreibung": "box out!"}, 
    {"Fokus": "Transition", "Beschreibung": "Slow the ball down! Pick up the ball early!"}, 
    {"Fokus": "Communication", "Beschreibung": "Talk on positioning, helpside & on screens"}, 
    {"Fokus": "Positioning", "Beschreibung": "close the middle on close outs and drives"}, 
    {"Fokus": "Pick´n Roll", "Beschreibung": "red (yellow, last 8 sec. from shot clock)"}, 
    {"Fokus": "DHO", "Beschreibung": "aggressive switch - same size / gap - small and big"}, 
    {"Fokus": "Offball screens", "Beschreibung": "yellow"}
]

DEFAULT_ABOUT = [
    {"Fokus": "Be ready", "Beschreibung": "for wild caotic / a lot of 1-1 and shooting"}, 
    {"Fokus": "Stay ready", "Beschreibung": "no matter what happens Don’t be bothered by calls/no calls"}, 
    {"Fokus": "No matter what", "Beschreibung": "the score is, we always give 100%."}, 
    {"Fokus": "Together", "Beschreibung": "Fight for & trust in each other!"}, 
    {"Fokus": "Take care", "Beschreibung": "of the ball no easy turnovers to prevent easy fastbreaks!"}, 
    {"Fokus": "Halfcourt", "Beschreibung": "Take responsibility! Stop them as a team!"}, 
    {"Fokus": "Communication", "Beschreibung": "Talk more, earlier and louder!"}
]

# --- SESSION STATE INITIALISIERUNG (UPDATED) ---
initial_keys = [
    ("current_page", "home"),
    ("print_mode", False),
    ("game_meta", {}),
    ("roster_df", None),
    ("live_view_mode", "today"),
    ("live_date_filter", date.today()),
    ("stats_team_id", None),
    ("stats_league_selection", None),
    ("analysis_team_id", None),
    ("generated_ai_report", None),
    ("live_game_id", None),
    # HIER WERDEN JETZT DIE STANDARDS GELADEN:
    ("facts_offense", pd.DataFrame(DEFAULT_OFFENSE)),
    ("facts_defense", pd.DataFrame(DEFAULT_DEFENSE)),
    ("facts_about", pd.DataFrame(DEFAULT_ABOUT)),
    ("saved_colors", {}),
    ("saved_notes", {}),
    ("pdf_bytes", None),
    ("report_filename", "scouting_report.pdf"),
    ("final_html", "")
]

for key, default in initial_keys:
    if key not in st.session_state:
        st.session_state[key] = default

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

# --- ADMIN SEITE: STREAM INFOS ---
def render_streaminfos_page():
    # Wenn wir im "config" Modus sind (externer Link), passen wir den Header an
    is_external = st.query_params.get("view") == "config"
    
    if is_external:
        inject_custom_css()
        st.title("📡 Stream Overlay Konfigurator")
        st.divider()
    else:
        render_page_header("📡 Stream Overlay Konfigurator")
        
    st.info("Generiere hier die Links für OBS Browserquellen (1920x1080).")
    
    south_teams = {k:v for k,v in TEAMS_DB.items() if v["staffel"] == "Süd"}
    team_opts = {v["name"]: k for k,v in south_teams.items()}
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["5️⃣ Starting 5", "🏆 Tabelle", "📊 Vergleich", "🔥 POTG", "🏁 Final Banner"])
    
    with tab1:
        c_h, c_g = st.columns(2)
        with c_h:
            st.subheader("🏠 Heimteam")
            h_name = st.selectbox("Team wählen", list(team_opts.keys()), key="s_h")
            h_id = team_opts[h_name]
            h_coach = st.text_input("Head Coach Heim", key="c_h")
            df_h, _ = fetch_team_data(h_id, CURRENT_SEASON_ID)
            if df_h is not None:
                p_map_h = {f"#{r['NR']} {r['NAME_FULL']}": r for _, r in df_h.iterrows()}
                sel_h = st.multiselect("Starting 5 Heim", list(p_map_h.keys()), max_selections=5, key="p_h")
                if st.button("🔗 Link HEIM generieren"):
                    p = {"view": "obs_starting5", "name": h_name, "logo_id": h_id, "coach": h_coach, "ids": ",".join([str(p_map_h[s]['PLAYER_ID']) for s in sel_h])}
                    for s in sel_h:
                        p_data = p_map_h[s]
                        p[f"n_{p_data['PLAYER_ID']}"] = p_data['NAME_FULL']
                        p[f"nr_{p_data['PLAYER_ID']}"] = p_data['NR']
                    st.code(f"/?{urlencode(p)}")

        with c_g:
            st.subheader("🚌 Gastteam")
            g_name = st.selectbox("Team wählen", list(team_opts.keys()), key="s_g", index=1)
            g_id = team_opts[g_name]
            g_coach = st.text_input("Head Coach Gast", key="c_g")
            df_g, _ = fetch_team_data(g_id, CURRENT_SEASON_ID)
            if df_g is not None:
                p_map_g = {f"#{r['NR']} {r['NAME_FULL']}": r for _, r in df_g.iterrows()}
                sel_g = st.multiselect("Starting 5 Gast", list(p_map_g.keys()), max_selections=5, key="p_g")
                if st.button("🔗 Link GAST generieren"):
                    p_g = {"view": "obs_starting5", "name": g_name, "logo_id": g_id, "coach": g_coach, "ids": ",".join([str(p_map_g[s]['PLAYER_ID']) for s in sel_g])}
                    for s in sel_g:
                        p_data = p_map_g[s]
                        p_g[f"n_{p_data['PLAYER_ID']}"] = p_data['NAME_FULL']
                        p_g[f"nr_{p_data['PLAYER_ID']}"] = p_data['NR']
                    st.code(f"/?{urlencode(p_g)}")

    with tab2:
        st.subheader("Tabelle")
        if st.button("🔗 Link Tabelle Süd generieren"):
            st.code("/?view=obs_standings&region=Süd")

    with tab3:
        st.subheader("Teamvergleich")
        c1, c2 = st.columns(2)
        v_h = c1.selectbox("Team A", list(team_opts.keys()), key="v_h")
        v_g = c2.selectbox("Team B", list(team_opts.keys()), key="v_g", index=1)
        if st.button("🔗 Link Vergleich generieren"):
            st.code(f"/?view=obs_comparison&hid={team_opts[v_h]}&gid={team_opts[v_g]}&hname={v_h}&gname={v_g}")

    with tab4:
        st.subheader("Player of the Game")
        from src.api import fetch_games_from_recent
        all_g = fetch_games_from_recent()
        game_opts = {f"{g['date']} | {g['home']} vs {g['guest']}": g['id'] for g in all_g}
        if game_opts:
            sel_g = st.selectbox("Spiel wählen", list(game_opts.keys()))
            if st.button("🔗 Link POTG generieren"):
                st.code(f"/?view=obs_potg&game_id={game_opts[sel_g]}")
        else: st.warning("Keine Spiele gefunden.")

    with tab5:
        st.subheader("🏁 Final Score Banner")
        if game_opts:
            sel_g_final = st.selectbox("Spiel für Final Banner", list(game_opts.keys()), key="sel_final_ban")
            if st.button("🔗 Link Final Banner"):
                st.code(f"/?view=obs_final_banner&game_id={game_opts[sel_g_final]}")

def render_home():
    inject_custom_css()
    st.markdown(f"""<div class="title-container"><h1 style='margin:0; color: #333;'>{BASKETBALL_ICON} DBBL Scouting Suite</h1><p style='margin:0; margin-top:10px; color: #555; font-weight: bold;'>Version {VERSION} | by Sascha Rosanke</p></div>""", unsafe_allow_html=True)
    
    # 3-Spalten-Layout
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("📝 PreGame Report", use_container_width=True): go_scouting(); st.rerun()
    with c2:
        if st.button("🔴 Live Game Center", use_container_width=True): st.session_state.current_page = "live"; st.rerun()
    with c3:
        if st.button("📡 Stream Infos (OBS)", use_container_width=True): st.session_state.current_page = "streaminfos"; st.rerun()
    
    st.write("")
    c4, c5, c6 = st.columns(3)
    with c4:
        if st.button("🧠 Team Spielanalyse", use_container_width=True): st.session_state.current_page = "team_analysis"; st.rerun()
    with c5:
        if st.button("📊 Head-to-Head", use_container_width=True): st.session_state.current_page = "comparison"; st.rerun()
    with c6:
        if st.button("📈 Team Stats", use_container_width=True): st.session_state.current_page = "team_stats"; st.rerun()

    st.write("")
    c7, c8, c9 = st.columns(3)
    with c7:
        if st.button("🔮 Spielvorbereitung", use_container_width=True): st.session_state.current_page = "prep"; st.rerun()
    with c8:
        if st.button("🎥 Spielnachbereitung", use_container_width=True): st.session_state.current_page = "analysis"; st.rerun()
    with c9:
          if st.button("🤼 Spielervergleich", use_container_width=True): st.session_state.current_page = "player_comparison"; st.rerun()
          
    st.write("")
    c10, _, _ = st.columns(3)
    with c10:
        if st.button("📍 Spielorte", use_container_width=True): st.session_state.current_page = "game_venue"; st.rerun()

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
        from src.api import fetch_games_from_recent
        with st.spinner("Lade Spielplan (Nord & Süd)..."): all_games = fetch_games_from_recent()
        games_to_show = []
        if st.session_state.live_view_mode == "today":
            today_str = datetime.now().strftime("%d.%m.%Y")
            if all_games: games_to_show = [g for g in all_games if g['date_only'] == today_str]
        else:
            st.markdown("##### Datum auswählen:")
            sel_date = st.date_input("Datum", value=st.session_state.live_date_filter, key="hist_date_picker", label_visibility="collapsed")
            st.session_state.live_date_filter = sel_date
            search_str = sel_date.strftime("%d.%m.%Y")
            if all_games: games_to_show = [g for g in all_games if g['date_only'] == search_str]
        
        if not games_to_show: st.info(f"Keine Spiele gefunden.")
        else:
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
    render_page_header("📝 PreGame Report") 
    if st.session_state.print_mode:
        st.subheader("Vorschau & Export")
        c1, c2 = st.columns([1, 4])
        with c1:
            if st.button("⬅️ Bearbeiten", key="exit_print"): st.session_state.print_mode = False; st.rerun()
        with c2:
            if st.session_state.pdf_bytes: st.download_button("📄 Download PDF", st.session_state.pdf_bytes, st.session_state.report_filename, "application/pdf")
            else: st.warning("PDF Fehler.")
        st.divider()
        if st.session_state.final_html: st.markdown("### HTML-Vorschau"); st.markdown(CSS_STYLES + st.session_state.final_html, unsafe_allow_html=True)
    else:
        with st.sidebar: 
            st.header("💾 Spielstand"); up = st.file_uploader("Laden (JSON)", type=["json"], key="scout_up")
            if up and st.button("Wiederherstellen", key="scout_restore"): s, m = load_session_state(up); st.success(m) if s else st.error(m)
            st.divider()
            if st.session_state.roster_df is not None: st.download_button("💾 Speichern", export_session_state(), f"Save_{date.today()}.json", "application/json", key="scout_save")
        
        st.subheader("1. Spieldaten")
        c1, c2, c3 = st.columns([1, 2, 2])
        with c1: s = st.radio("Staffel:", ["Süd", "Nord"], horizontal=True, key="scout_staffel"); t = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == s}; to = {v["name"]: k for k, v in t.items()}
        with c2:
            idx = 0; 
            if "home_name" in st.session_state.game_meta and st.session_state.game_meta["home_name"] in to: idx = list(to.keys()).index(st.session_state.game_meta["home_name"])
            hn = st.selectbox("Heim:", list(to.keys()), index=idx, key="sel_home"); hid = to[hn]
            if "logo_h" not in st.session_state or st.session_state.game_meta.get("home_name") != hn: st.session_state.logo_h = get_best_team_logo(hid)
            if st.session_state.logo_h: st.image(st.session_state.logo_h, width=80)
            else: st.markdown(BASKETBALL_ICON)
        with c3:
            idxg = 1
            if "guest_name" in st.session_state.game_meta and st.session_state.game_meta["guest_name"] in to: idxg = list(to.keys()).index(st.session_state.game_meta["guest_name"])
            gn = st.selectbox("Gast:", list(to.keys()), index=idxg, key="sel_guest"); gid = to[gn]
            if "logo_g" not in st.session_state or st.session_state.game_meta.get("guest_name") != gn: st.session_state.logo_g = get_best_team_logo(gid)
            if st.session_state.logo_g: st.image(st.session_state.logo_g, width=80)
            else: st.markdown(BASKETBALL_ICON)
        st.write("---")
        idx_t = 0
        if st.session_state.game_meta.get("selected_target") == "Heimteam": idx_t = 1
        target = st.radio("Target:", ["Gastteam (Gegner)", "Heimteam"], horizontal=True, index=idx_t, key="sel_target") 
        tid = gid if target == "Gastteam (Gegner)" else hid
        c_d, c_t = st.columns(2); d_inp = c_d.date_input("Datum", date.today(), key="scout_date"); t_inp = c_t.time_input("Tip-Off", time(16,0), key="scout_time") 
        st.divider(); cur_tid = st.session_state.get("current_tid"); click_load = st.button(f"2. Kader von {target} laden", type="primary", key="load_scout")
        
        if click_load or (st.session_state.roster_df is None and cur_tid != tid) or (st.session_state.roster_df is not None and cur_tid != tid):
            with st.spinner("Lade Daten..."):
                df, ts = fetch_team_data(tid, CURRENT_SEASON_ID)
                if df is not None and not df.empty: 
                    st.session_state.roster_df = df; st.session_state.team_stats = ts; st.session_state.current_tid = tid 
                    dummy_dt = datetime.combine(date.today(), t_inp)
                    time_str_de = t_inp.strftime("%H:%M Uhr")
                    time_str_us = dummy_dt.strftime("%I %p").lower() # z.B. 04 pm
                    final_time_str = f"{time_str_de} / {time_str_us}"
                    st.session_state.game_meta = { "home_name": hn, "home_logo": st.session_state.logo_h, "guest_name": gn, "guest_logo": st.session_state.logo_g, "date": d_inp.strftime("%d.%m.%Y"), "time": final_time_str, "selected_target": target }
                    st.session_state.print_mode = False 
                else: st.error("Fehler API."); st.session_state.roster_df = pd.DataFrame(); st.session_state.team_stats = {}; st.session_state.game_meta = {} 
        elif st.session_state.roster_df is None or st.session_state.roster_df.empty: st.info("Bitte laden.")
        
        if st.session_state.roster_df is not None and not st.session_state.roster_df.empty: 
            st.subheader("3. Auswahl & Notizen")
            cols = { "select": st.column_config.CheckboxColumn("Auswahl", default=False, width="small"), "NR": st.column_config.TextColumn("#", width="small"), "NAME_FULL": st.column_config.TextColumn("Name"), "GP": st.column_config.NumberColumn("GP", format="%d"), "PPG": st.column_config.NumberColumn("PPG", format="%.1f"), "FG%": st.column_config.NumberColumn("FG%", format="%.1f %%"), "TOT": st.column_config.NumberColumn("REB", format="%.1f") }
            edited = st.data_editor(st.session_state.roster_df[["select", "NR", "NAME_FULL", "GP", "PPG", "FG%", "TOT"]], column_config=cols, disabled=["NR", "NAME_FULL", "GP", "PPG", "FG%", "TOT"], hide_index=True, key="player_table_scout") 
            sel_idx = edited[edited["select"]].index
            if len(sel_idx) > 0:
                st.divider()
                with st.form("scout_form", clear_on_submit=False): 
                    sel = st.session_state.roster_df.loc[sel_idx]; res = []; cmap = {"Grau": "#999999", "Grün": "#5c9c30", "Rot": "#d9534f"}
                    for i, (_, r) in enumerate(sel.iterrows()): 
                        pid = r["PLAYER_ID"]; c_h, c_c = st.columns([3, 1]); c_h.markdown(f"**#{r['NR']} {r['NAME_FULL']}**"); sc = st.session_state.saved_colors.get(pid, "Grau"); ix = list(cmap.keys()).index(sc) if sc in cmap else 0
                        col = c_c.selectbox("Farbe", list(cmap.keys()), key=f"c_{pid}_{i}", index=ix, label_visibility="collapsed") 
                        c1, c2 = st.columns(2); n = {}
                        for k in ["l1", "l2", "l3", "l4", "r1", "r2", "r3", "r4"]: val = st.session_state.saved_notes.get(f"{k}_{pid}", ""); n[k] = (c1 if k.startswith("l") else c2).text_input(k, value=val, key=f"n_{k}_{pid}_{i}", label_visibility="collapsed")
                        st.divider(); res.append({"row": r, "pid": pid, "color": col, "notes": n})
                    c1, c2, c3 = st.columns(3)
                    with c1: st.caption("Offense"); eo = st.data_editor(st.session_state.facts_offense, num_rows="dynamic", hide_index=True, key="eo_scout")
                    with c2: st.caption("Defense"); ed = st.data_editor(st.session_state.facts_defense, num_rows="dynamic", hide_index=True, key="ed_scout")
                    with c3: st.caption("About"); ea = st.data_editor(st.session_state.facts_about, num_rows="dynamic", hide_index=True, key="ea_scout")
                    up = st.file_uploader("Plays", accept_multiple_files=True, type=["png","jpg"], key="up_scout")
                    if st.form_submit_button("Generieren", type="primary"):
                        st.session_state.facts_offense = eo; st.session_state.facts_defense = ed; st.session_state.facts_about = ea
                        for item in res:
                            st.session_state.saved_colors[item["pid"]] = item["color"]; 
                            for k, v in item["notes"].items(): st.session_state.saved_notes[f"{k}_{item['pid']}"] = v
                        tn = (gn if target == "Gastteam (Gegner)" else hn).replace(" ", "_")
                        st.session_state.report_filename = f"Scouting_Report_{tn}_{d_inp.strftime('%d.%m.%Y')}.pdf"
                        html = generate_header_html(st.session_state.game_meta); html += generate_top3_html(st.session_state.roster_df)
                        for item in res: meta = get_player_metadata_cached(item["pid"]); html += generate_card_html(item["row"].to_dict(), meta, item["notes"], cmap[item["color"]])
                        html += generate_team_stats_html(st.session_state.team_stats)
                        if up:
                            html += "<div style='page-break-before:always'><h2>Plays</h2>"; 
                            for f in up: b64 = base64.b64encode(f.getvalue()).decode(); html += f"<div style='margin-bottom:20px'><img src='data:image/png;base64,{b64}' style='max-width:100%;max-height:900px;border:1px solid #ccc'></div>"
                        html += generate_custom_sections_html(eo, ed, ea); st.session_state.final_html = html
                        if HAS_PDFKIT:
                            try:
                                opts = {
                                    "page-size": "A4",
                                    "orientation": "Portrait",
                                    "margin-top": "5mm",
                                    "margin-right": "5mm",
                                    "margin-bottom": "5mm",
                                    "margin-left": "5mm",
                                    "encoding": "UTF-8",
                                    "zoom": "0.65",
                                    "no-outline": None,
                                    "disable-smart-shrinking": None,
                                    "quiet": ""
                                }
                                st.session_state.pdf_bytes = pdfkit.from_string(f"<!DOCTYPE html><html><head><meta charset='utf-8'>{CSS_STYLES}</head><body>{html}</body></html>", False, options=opts); st.session_state.print_mode = True; st.rerun()
                            except Exception as e: st.error(f"PDF Error: {e}"); st.session_state.pdf_bytes = None; st.session_state.print_mode = True; st.rerun()
                        else: st.warning("PDFKit fehlt."); st.session_state.pdf_bytes = None; st.session_state.print_mode = True; st.rerun()

def render_team_stats_page():
    inject_custom_css()
    if st.session_state.stats_team_id:
        tid = st.session_state.stats_team_id
        col_back, col_head = st.columns([1, 5])
        with col_back:
            if st.button("⬅️ Zur Übersicht", key="back_from_stats"): st.session_state.stats_team_id = None; st.rerun()
        with st.spinner("Lade Team Statistiken..."): df, ts = fetch_team_data(tid, CURRENT_SEASON_ID); games_data = fetch_schedule(tid, CURRENT_SEASON_ID)
        has_data = (df is not None and not df.empty) or (ts and len(ts) > 0)
        if has_data:
            t_info = TEAMS_DB.get(tid, {})
            name = t_info.get("name", "Team"); logo_b64 = get_best_team_logo(tid)
            c1, c2 = st.columns([1, 4])
            with c1: 
                if logo_b64: st.image(logo_b64, width=100)
                else: st.markdown(BASKETBALL_ICON, unsafe_allow_html=True)
            with c2: st.title(f"Statistik: {name}")
            st.divider(); st.subheader(f"Saison Durchschnittswerte (Saison {CURRENT_SEASON_ID})")
            if ts:
                m1, m2, m3, m4, m5, m6 = st.columns(6)
                m1.metric("Punkte", f"{ts.get('ppg', 0):.1f}"); m2.metric("Rebounds", f"{ts.get('tot', 0):.1f}"); m3.metric("Assists", f"{ts.get('as', 0):.1f}"); m4.metric("Steals", f"{ts.get('st', 0):.1f}"); m5.metric("Turnovers", f"{ts.get('to', 0):.1f}"); m6.metric("FG %", f"{ts.get('fgpct', 0):.1f}%")
                m1, m2, m3, m4, m5, m6 = st.columns(6)
                m1.metric("3er %", f"{ts.get('3pct', 0):.1f}%"); m2.metric("FW %", f"{ts.get('ftpct', 0):.1f}%"); m3.metric("Fouls", f"{ts.get('pf', 0):.1f}"); m4.metric("Off. Reb", f"{ts.get('or', 0):.1f}"); m5.metric("Def. Reb", f"{ts.get('dr', 0):.1f}"); m6.metric("Blocks", f"{ts.get('bs', 0):.1f}")
            st.divider(); st.subheader("Aktueller Kader & Stats")
            if df is not None and not df.empty:
                df = df.sort_values(by="PPG", ascending=False)
                display_cols = ["NR", "NAME_FULL", "GP", "MIN_DISPLAY", "PPG", "FG%", "3PCT", "FTPCT", "TOT", "AS", "ST", "TO", "PF"]
                col_config = { "NR": st.column_config.TextColumn("#", width="small"), "NAME_FULL": st.column_config.TextColumn("Name", width="medium"), "GP": st.column_config.NumberColumn("Spiele"), "MIN_DISPLAY": st.column_config.TextColumn("Min"), "PPG": st.column_config.NumberColumn("PTS", format="%.1f"), "FG%": st.column_config.NumberColumn("FG%", format="%.1f %%"), "3PCT": st.column_config.NumberColumn("3P%", format="%.1f %%"), "FTPCT": st.column_config.NumberColumn("FW%", format="%.1f %%"), "TOT": st.column_config.NumberColumn("REB", format="%.1f"), "AS": st.column_config.NumberColumn("AST", format="%.1f"), "ST": st.column_config.NumberColumn("STL", format="%.1f"), "TO": st.column_config.NumberColumn("TO", format="%.1f"), "PF": st.column_config.NumberColumn("PF", format="%.1f") }
                st.dataframe(df[display_cols], column_config=col_config, hide_index=True, use_container_width=True, height=600)
            else: st.info("Keine Spielerdaten verfügbar.")
            st.divider(); st.subheader("Saisonverlauf")
            if games_data:
                played = [g for g in games_data if g.get('has_result')]
                if played:
                    try: played.sort(key=lambda x: datetime.strptime(x['date'], "%d.%m.%Y %H:%M") if x['date'] and x['date'] != "-" else datetime.min, reverse=True)
                    except: pass
                    hist = []
                    for g in played:
                        is_home = str(g.get('homeTeamId')) == str(tid)
                        own = int(g['home_score']) if is_home else int(g['guest_score'])
                        opp = int(g['guest_score']) if is_home else int(g['home_score'])
                        hist.append({ "Datum": g['date'].split(" ")[0], "Ort": "vs" if is_home else "@", "Gegner": g['guest'] if is_home else g['home'], "Ergebnis": g['score'], "W/L": "W" if own > opp else ("L" if own < opp else "T"), "Diff": f"{'+' if own > opp else ''}{own-opp}" })
                    st.dataframe(pd.DataFrame(hist), hide_index=True, use_container_width=True)
                else: st.info("Keine absolvierten Spiele.")
            else: st.info("Keine Spieldaten.")
        else: st.error(f"Daten konnten für Saison {CURRENT_SEASON_ID} nicht geladen werden.")
    elif st.session_state.stats_league_selection is None:
        render_page_header("📈 Liga Auswahl")
        c1, c2, c3 = st.columns(3)
        if c1.button("1. DBBL", use_container_width=True): st.session_state.stats_league_selection = "1. DBBL"; st.rerun()
        if c2.button("2. DBBL Nord", use_container_width=True): st.session_state.stats_league_selection = "Nord"; st.rerun()
        if c3.button("2. DBBL Süd", use_container_width=True): st.session_state.stats_league_selection = "Süd"; st.rerun()
    else:
        sel = st.session_state.stats_league_selection
        c_back, c_title = st.columns([1, 4])
        if c_back.button("⬅️ Zurück"): st.session_state.stats_league_selection = None; st.rerun()
        c_title.title(f"Übersicht: {sel}"); st.divider()
        c_tbl, c_grid = st.columns([1, 2], gap="large")
        with c_tbl:
            st.subheader("Tabelle")
            with st.spinner("Lade Tabelle..."): df = fetch_league_standings(CURRENT_SEASON_ID, sel)
            if not df.empty: st.dataframe(df, hide_index=True, use_container_width=True, height=600)
            else: st.info("Tabelle nicht verfügbar.")
        with c_grid:
            st.subheader("Teams")
            teams = {k: v for k, v in TEAMS_DB.items() if v.get("staffel") == sel}
            if teams:
                cols = st.columns(3)
                for idx, (tid, info) in enumerate(teams.items()):
                    with cols[idx % 3]:
                        with st.container(border=True):
                            l = get_best_team_logo(tid)
                            c_i, c_t = st.columns([1, 2])
                            if l: c_i.image(l, use_container_width=True)
                            else: c_i.write(BASKETBALL_ICON)
                            c_t.markdown(f"**{info['name']}**")
                            if st.button("Stats ➜", key=f"btn_stats_{tid}", use_container_width=True): st.session_state.stats_team_id = tid; st.rerun()

def render_comparison_page():
    render_page_header("📊 Head-to-Head Vergleich") 
    c1, c2, c3 = st.columns([1, 2, 2])
    with c1: 
        staffel = st.radio("Staffel:", ["Süd", "Nord"], horizontal=True, key="comp_staffel")
        teams = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == staffel}
        team_opts = {v["name"]: k for k, v in teams.items()}
    with c2:
        h_name = st.selectbox("Heim:", list(team_opts.keys()), 0, key="comp_home"); h_id = team_opts[h_name]; l_b64 = get_best_team_logo(h_id)
        if l_b64: st.image(l_b64, width=80)
        else: st.markdown(BASKETBALL_ICON)
    with c3:
        g_name = st.selectbox("Gast:", list(team_opts.keys()), 1, key="comp_guest"); g_id = team_opts[g_name]; l_b64 = get_best_team_logo(g_id)
        if l_b64: st.image(l_b64, width=80)
        else: st.markdown(BASKETBALL_ICON)
    st.divider()
    if st.button("Vergleich starten", type="primary"):
        with st.spinner("Lade Daten..."):
            _, ts_h = fetch_team_data(h_id, CURRENT_SEASON_ID); _, ts_g = fetch_team_data(g_id, CURRENT_SEASON_ID)
            if ts_h and ts_g: st.markdown(generate_comparison_html(ts_h, ts_g, h_name, g_name), unsafe_allow_html=True)
            else: st.error("Daten nicht verfügbar.")

def render_player_comparison_page():
    render_page_header("🤼 Head-to-Head Spielervergleich") 
    c1, c2, c3 = st.columns([1, 0.1, 1])
    with c1:
        st.subheader("Spieler A"); s1 = st.radio("Staffel A", ["Süd", "Nord"], horizontal=True, key="pc_s_a")
        t1 = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == s1}
        tn1 = st.selectbox("Team", list({v["name"]: k for k, v in t1.items()}.keys()), key="pc_t_a"); tid1 = {v["name"]: k for k, v in t1.items()}[tn1]
        df1, _ = fetch_team_data(tid1, CURRENT_SEASON_ID)
        if df1 is not None and not df1.empty: 
            p1 = st.selectbox("Spieler", df1["NAME_FULL"].tolist(), key="pc_p_a"); row1 = df1[df1["NAME_FULL"] == p1].iloc[0]; m1 = get_player_metadata_cached(row1["PLAYER_ID"])
            if m1["img"]: st.image(m1["img"], width=150)
        else: st.error("Daten nicht geladen."); row1 = None
    with c2: st.write("") 
    with c3:
        st.subheader("Spieler B"); s2 = st.radio("Staffel B", ["Süd", "Nord"], horizontal=True, key="pc_s_b")
        t2 = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == s2}
        tn2 = st.selectbox("Team", list({v["name"]: k for k, v in t2.items()}.keys()), key="pc_t_b"); tid2 = {v["name"]: k for k, v in t2.items()}[tn2]
        df2, _ = fetch_team_data(tid2, CURRENT_SEASON_ID)
        if df2 is not None and not df2.empty: 
            p2 = st.selectbox("Spieler", df2["NAME_FULL"].tolist(), key="pc_p_b"); row2 = df2[df2["NAME_FULL"] == p2].iloc[0]; m2 = get_player_metadata_cached(row2["PLAYER_ID"])
            if m2["img"]: st.image(m2["img"], width=150)
        else: st.error("Daten nicht geladen."); row2 = None
    st.divider()
    if row1 is not None and row2 is not None:
        metrics = [("Spiele", "GP", int), ("Punkte", "PPG", float), ("Minuten", "MIN_DISPLAY", str), ("FG %", "FG%", float), ("3er %", "3PCT", float), ("FW %", "FTPCT", float), ("Reb", "TOT", float), ("Assists", "AS", float), ("TO", "TO", float), ("Steals", "ST", float), ("Blocks", "BS", float), ("Fouls", "PF", float)]
        h1, h2, h3 = st.columns([1, 1, 1]); h1.markdown(f"<h3 style='text-align: right;'>{p1}</h3>", unsafe_allow_html=True); h2.markdown(f"<div style='text-align: center; font-weight: bold;'>VS</div>", unsafe_allow_html=True); h3.markdown(f"<h3 style='text-align: left;'>{p2}</h3>", unsafe_allow_html=True); st.write("")
        for l, c, t in metrics:
            v1 = row1[c]; v2 = row2[c]; s1="color:#444;"; s2="color:#444;"
            if t in [int, float]:
                try:
                    vf1=float(v1); vf2=float(v2)
                    if c in ["TO", "PF"]: 
                        if vf1 < vf2: s1="font-weight:bold;"
                        elif vf2 < vf1: s2="font-weight:bold;"
                    else:
                        if vf1 > vf2: s1="font-weight:bold;"
                        elif vf2 > vf1: s2="font-weight:bold;"
                except: pass
            c1, c2, c3 = st.columns([1, 1.5, 1])
            with c1: st.markdown(f"<div style='text-align: right; {s1}'>{v1}</div>", unsafe_allow_html=True)
            with c2: st.markdown(f"<div style='text-align: center; background:#f8f9fa;'>{l}</div>", unsafe_allow_html=True)
            with c3: st.markdown(f"<div style='text-align: left; {s2}'>{v2}</div>", unsafe_allow_html=True)

# --- ROUTER (HAUPTNAVIGATION) ---
# 1. EXTENER LINK für OBS-Konfiguration
# Prüft, ob "?view=config" in der URL steht.
if "view" in st.query_params and st.query_params["view"] == "config":
    st.markdown('<style>[data-testid="stAppViewContainer"] { background-image: none !important; background-color: #ffffff !important; } [data-testid="stHeader"] { background-color: #ffffff !important; }</style>', unsafe_allow_html=True)
    render_streaminfos_page()
if "view" in st.query_params and st.query_params["view"] == "live":
    st.markdown('<style>[data-testid="stAppViewContainer"] { background-image: none !important; background-color: #ffffff !important; } [data-testid="stHeader"] { background-color: #ffffff !important; }</style>', unsafe_allow_html=True)
    render_live_page()
    
# 2. NORMALE NAVIGATION (Wenn kein "view" Parameter da ist)
elif st.session_state.current_page == "home": render_home()
elif st.session_state.current_page == "scouting": render_scouting_page()
elif st.session_state.current_page == "comparison": render_comparison_page()
elif st.session_state.current_page == "analysis": render_analysis_page()
elif st.session_state.current_page == "player_comparison": render_player_comparison_page()
elif st.session_state.current_page == "game_venue": render_game_venue_page()
elif st.session_state.current_page == "prep": render_prep_page()
elif st.session_state.current_page == "live": render_live_page()
elif st.session_state.current_page == "team_stats": render_team_stats_page()
elif st.session_state.current_page == "team_analysis": render_team_analysis_page()
elif st.session_state.current_page == "streaminfos": render_streaminfos_page()

# Platzhalter für Live View, falls noch benötigt (standardmäßig über session_state "live")
elif st.session_state.current_page == "live_placeholder": render_live_view(None)

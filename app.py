# --- START OF FILE app.py ---

import streamlit as st
import pandas as pd
from datetime import datetime, date, time 
import time as time_module 
from urllib.parse import quote_plus 

try:
    import pdfkit
    HAS_PDFKIT = True
except ImportError:
    HAS_PDFKIT = False

from src.config import VERSION, TEAMS_DB, SEASON_ID, CSS_STYLES
from src.utils import get_logo_url, optimize_image_base64
from src.api import (
    fetch_team_data, get_player_metadata_cached, fetch_schedule, 
    fetch_game_boxscore, fetch_game_details, fetch_team_info_basic 
)
from src.html_gen import (
    generate_header_html, generate_top3_html, generate_card_html, 
    generate_team_stats_html, generate_custom_sections_html,
    generate_comparison_html
)
from src.state_manager import export_session_state, load_session_state

# HIER WERDEN ALLE BENÖTIGTEN FUNKTIONEN AUS analysis_ui IMPORTIERT
from src.analysis_ui import (
    render_game_header, render_boxscore_table_pro, render_charts_and_stats, 
    get_team_name, render_game_top_performers, generate_game_summary,
    generate_complex_ai_prompt, render_full_play_by_play, run_openai_generation,
    render_prep_dashboard, render_live_view 
)

st.set_page_config(page_title=f"DBBL Scouting Pro {VERSION}", layout="wide", page_icon="🏀")

# --- SESSION STATE ---
for key, default in [
    ("current_page", "home"), ("print_mode", False), ("final_html", ""), ("pdf_bytes", None),
    ("roster_df", None), ("team_stats", None), ("game_meta", {}),
    ("report_filename", "scouting_report.pdf"), ("saved_notes", {}), ("saved_colors", {}),
    ("facts_offense", pd.DataFrame([{"Fokus": "Run", "Beschreibung": "fastbreaks"}])),
    ("facts_defense", pd.DataFrame([{"Fokus": "Rebound", "Beschreibung": "box out!"}])),
    ("facts_about", pd.DataFrame([{"Fokus": "Together", "Beschreibung": "Fight!"}])),
    ("selected_game_id", None), ("generated_ai_report", None), ("live_game_id", None)
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

# --- STANDARD-SEITENHEADER ---
def render_page_header(page_title):
    header_col1, header_col2 = st.columns([1, 4])
    with header_col1:
        st.button("🏠 Home", on_click=go_home, key=f"home_button_header_{st.session_state.current_page}")
    with header_col2:
        st.markdown("<h3 style='text-align: right; color: #666;'>DBBL Scouting Pro by Sascha Rosanke</h3>", unsafe_allow_html=True)
    st.title(page_title) 
    st.divider()

# ==========================================
# SEITE 1: HOME
# ==========================================
def render_home():
    st.markdown("""<style>[data-testid="stAppViewContainer"]::before {content:"";position:fixed;top:0;left:0;width:100%;height:100%;background-image:url("https://cdn.pixabay.com/photo/2022/11/22/20/25/ball-7610545_1280.jpg");background-size:cover;opacity:0.3;z-index:-1;} div.stButton>button{width:100%;height:4em;font-size:18px;font-weight:bold;border-radius:10px;box-shadow:0px 4px 6px rgba(0,0,0,0.1);}</style>""", unsafe_allow_html=True)
    st.markdown("<div style='text-align: center; margin-top: 50px;'><h1>🏀 DBBL Scouting Suite</h1></div>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center; color: #333; font-weight: bold;'>Version {VERSION} | by Sascha Rosanke</p>", unsafe_allow_html=True)
    st.write(""); st.write("")
    _, col_center, _ = st.columns([1, 2, 1])
    with col_center:
        c1, c2 = st.columns(2)
        with c1: 
            if st.button("📊 Teamvergleich", use_container_width=True): go_comparison(); st.rerun()
        with c2: 
            if st.button("🤼 Spielervergleich", use_container_width=True): go_player_comparison(); st.rerun()
        st.write("")
        c3, c4 = st.columns(2)
        with c3: 
            if st.button("📝 Scouting Report", use_container_width=True): go_scouting(); st.rerun()
        with c4: 
            if st.button("🎥 Spielnachbereitung", use_container_width=True): go_analysis(); st.rerun()
        st.write("")
        c5, c6 = st.columns(2)
        with c5:
             if st.button("🔮 Spielvorbereitung", use_container_width=True): go_prep(); st.rerun()
        with c6:
             if st.button("🔴 Live Game", use_container_width=True): go_live(); st.rerun()
        st.write("")
        if st.button("📍 Spielorte", use_container_width=True): go_game_venue(); st.rerun() 

# ==========================================
# SEITE 2: TEAMVERGLEICH
# ==========================================
def render_comparison_page():
    render_page_header("📊 Head-to-Head Vergleich") 
    c1, c2, c3 = st.columns([1, 2, 2])
    with c1: 
        staffel = st.radio("Staffel:", ["Süd", "Nord"], horizontal=True, key="comp_staffel")
        teams_filtered = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == staffel}
        team_options = {v["name"]: k for k, v in teams_filtered.items()}
    with c2:
        home_name = st.selectbox("Heim:", list(team_options.keys()), 0, key="comp_home")
        home_id = team_options[home_name]
        st.image(optimize_image_base64(get_logo_url(home_id, SEASON_ID)), width=60)
    with c3:
        guest_name = st.selectbox("Gast:", list(team_options.keys()), 1, key="comp_guest")
        guest_id = team_options[guest_name]
        st.image(optimize_image_base64(get_logo_url(guest_id, SEASON_ID)), width=60)
    st.divider()
    if st.button("Vergleich starten", type="primary"):
        with st.spinner("Lade Daten..."):
            _, ts_home = fetch_team_data(home_id, SEASON_ID)
            _, ts_guest = fetch_team_data(guest_id, SEASON_ID)
            if ts_home and ts_guest:
                comp_html = generate_comparison_html(ts_home, ts_guest, home_name, guest_name)
                st.markdown(comp_html, unsafe_allow_html=True)
            else:
                st.error("Daten nicht verfügbar.")

# ==========================================
# SEITE: SPIELERVERGLEICH
# ==========================================
def render_player_comparison_page():
    render_page_header("🤼 Head-to-Head Spielervergleich") 
    col_left, col_mid, col_right = st.columns([1, 0.1, 1])
    with col_left:
        st.subheader("Spieler A")
        staffel_a = st.radio("Staffel A", ["Süd", "Nord"], horizontal=True, key="pc_s_a")
        teams_a = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == staffel_a}
        t_name_a = st.selectbox("Team", list({v["name"]: k for k, v in teams_a.items()}.keys()), key="pc_t_a")
        tid_a = {v["name"]: k for k, v in teams_a.items()}[t_name_a]
        df_a, _ = fetch_team_data(tid_a, SEASON_ID)
        if df_a is not None and not df_a.empty: 
            p_opts_a = df_a["NAME_FULL"].tolist()
            p_name_a = st.selectbox("Spieler", p_opts_a, key="pc_p_a")
            row_a = df_a[df_a["NAME_FULL"] == p_name_a].iloc[0]
            meta_a = get_player_metadata_cached(row_a["PLAYER_ID"])
            if meta_a["img"]: st.image(meta_a["img"], width=150)
        else:
            st.error("Daten für Spieler A nicht geladen.")
            row_a = None
    with col_mid: st.write("") 
    with col_right:
        st.subheader("Spieler B")
        staffel_b = st.radio("Staffel B", ["Süd", "Nord"], horizontal=True, key="pc_s_b")
        teams_b = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == staffel_b}
        t_name_b = st.selectbox("Team", list({v["name"]: k for k, v in teams_b.items()}.keys()), key="pc_t_b")
        tid_b = {v["name"]: k for k, v in teams_b.items()}[t_name_b]
        df_b, _ = fetch_team_data(tid_b, SEASON_ID)
        if df_b is not None and not df_b.empty: 
            p_opts_b = df_b["NAME_FULL"].tolist()
            p_name_b = st.selectbox("Spieler", p_opts_b, key="pc_p_b")
            row_b = df_b[df_b["NAME_FULL"] == p_name_b].iloc[0]
            meta_b = get_player_metadata_cached(row_b["PLAYER_ID"])
            if meta_b["img"]: st.image(meta_b["img"], width=150)
        else:
            st.error("Daten für Spieler B nicht geladen.")
            row_b = None
    st.divider()
    if row_a is not None and row_b is not None:
        metrics = [("Spiele", "GP", int), ("Punkte", "PPG", float), ("Minuten", "MIN_DISPLAY", str), ("FG %", "FG%", float), ("3er %", "3PCT", float), ("FW %", "FTPCT", float), ("Reb", "TOT", float), ("Assists", "AS", float), ("TO", "TO", float), ("Steals", "ST", float), ("Blocks", "BS", float), ("Fouls", "PF", float)]
        h1, h2, h3 = st.columns([1, 1, 1])
        h1.markdown(f"<h3 style='text-align: right;'>{p_name_a}</h3>", unsafe_allow_html=True)
        h2.markdown(f"<div style='text-align: center; font-weight: bold;'>VS</div>", unsafe_allow_html=True)
        h3.markdown(f"<h3 style='text-align: left;'>{p_name_b}</h3>", unsafe_allow_html=True)
        st.write("")
        for label, col, dtype in metrics:
            val_a = row_a[col]; val_b = row_b[col]
            style_a = "color: #444;"; style_b = "color: #444;"
            if dtype in [int, float]:
                try:
                    va = float(val_a); vb = float(val_b)
                    if col in ["TO", "PF"]:
                        if va < vb: style_a = "font-weight: bold;"
                        elif vb < va: style_b = "font-weight: bold;"
                    else:
                        if va > vb: style_a = "font-weight: bold;"
                        elif vb > va: style_b = "font-weight: bold;"
                except: pass
            c1, c2, c3 = st.columns([1, 1.5, 1])
            with c1: st.markdown(f"<div style='text-align: right; {style_a}'>{val_a}</div>", unsafe_allow_html=True)
            with c2: st.markdown(f"<div style='text-align: center; background:#f8f9fa;'>{label}</div>", unsafe_allow_html=True)
            with c3: st.markdown(f"<div style='text-align: left; {style_b}'>{val_b}</div>", unsafe_allow_html=True)

def render_analysis_page():
    render_page_header("🎥 Spielnachbereitung") 
    c1, c2 = st.columns([1, 2])
    with c1:
        staffel = st.radio("Staffel", ["Süd", "Nord"], horizontal=True, key="ana_staffel")
        teams_filtered = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == staffel}
        team_options = {v["name"]: k for k, v in teams_filtered.items()}
    with c2:
        my_team_name = st.selectbox("Dein Team:", list(team_options.keys()), key="ana_team")
        my_team_id = team_options[my_team_name]
    if my_team_id:
        games = fetch_schedule(my_team_id, SEASON_ID)
        if games:
            game_opts = {f"{g['date']} | {g['home']} vs {g['guest']} ({g['score']})": g['id'] for g in games}
            selected_label = st.selectbox("Wähle ein Spiel:", list(game_opts.keys()), key="ana_game_select")
            selected_id = game_opts[selected_label]
            if st.button("Analyse laden", type="primary"):
                st.session_state.selected_game_id = selected_id
                if "generated_ai_report" in st.session_state: del st.session_state["generated_ai_report"]
            if st.session_state.selected_game_id == selected_id:
                st.divider()
                with st.spinner("Lade Boxscore & Details..."):
                    box = fetch_game_boxscore(selected_id)
                    details = fetch_game_details(selected_id)
                    if box and details: 
                        box["venue"] = details.get("venue"); box["result"] = details.get("result"); box["referee1"] = details.get("referee1"); box["referee2"] = details.get("referee2"); box["referee3"] = details.get("referee3"); box["scheduledTime"] = details.get("scheduledTime"); box["attendance"] = details.get("result", {}).get("spectators"); box["id"] = details.get("id") 
                        render_game_header(box)
                        st.markdown("### 📝 Spielberichte & PBP")
                        tab_simple, tab_prompt, tab_pbp = st.tabs(["⚡ Kurzbericht", "📋 Prompt Kopieren", "📜 Play-by-Play"])
                        with tab_simple:
                            report_text = generate_game_summary(box)
                            st.markdown(report_text)
                            st.caption("Regelbasierter Kurzbericht.")
                            st.divider()
                            h_name = get_team_name(box.get("homeTeam", {}), "Heim"); g_name = get_team_name(box.get("guestTeam", {}), "Gast")
                            h_coach = box.get("homeTeam", {}).get("headCoachName", "-"); g_coach = box.get("guestTeam", {}).get("headCoachName", "-")
                            render_boxscore_table_pro(box.get("homeTeam", {}).get("playerStats", []), box.get("homeTeam", {}).get("gameStat", {}), h_name, h_coach)
                            st.write("")
                            render_boxscore_table_pro(box.get("guestTeam", {}).get("playerStats", []), box.get("guestTeam", {}).get("gameStat", {}), g_name, g_coach)
                            st.divider(); render_game_top_performers(box); st.divider(); render_charts_and_stats(box)
                        with tab_prompt:
                            st.info("Kopiere diesen Text in ChatGPT:")
                            ai_prompt = generate_complex_ai_prompt(box)
                            st.code(ai_prompt, language="text")
                        with tab_pbp:
                            render_full_play_by_play(box)
                    else: st.error("Konnte Spieldaten nicht laden.")
        else: st.warning("Keine Spiele gefunden.")

def render_game_venue_page():
    render_page_header("📍 Spielorte der Teams") 
    c1, c2 = st.columns([1, 2])
    with c1:
        staffel = st.radio("Staffel", ["Süd", "Nord"], horizontal=True, key="venue_staffel")
        teams_filtered = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == staffel}
        team_options = {v["name"]: k for k, v in teams_filtered.items()}
    with c2:
        selected_team_name = st.selectbox("Wähle ein Team:", list(team_options.keys()), key="venue_team_select")
        selected_team_id = team_options[selected_team_name]
    st.divider()
    if selected_team_id:
        st.subheader(f"Standard-Heimspielort von {selected_team_name}")
        with st.spinner(f"Lade Standard-Spielort-Details für {selected_team_name}..."):
            team_venue_info = fetch_team_info_basic(selected_team_id)
            main_venue_data = team_venue_info.get("venue") if team_venue_info else None
            if main_venue_data:
                main_venue_name = main_venue_data.get("name", "Nicht verfügbar")
                main_venue_address = main_venue_data.get("address", "Nicht verfügbar")
                st.markdown(f"**Halle:** {main_venue_name}")
                st.markdown(f"**Adresse:** {main_venue_address}")
                if main_venue_address != "Nicht verfügbar":
                    maps_query = quote_plus(f"{main_venue_name}, {main_venue_address}")
                    maps_url = f"https://www.google.com/maps/search/?api=1&query={maps_query}"
                    st.markdown(f"**Route planen:** [Google Maps öffnen]({maps_url})", unsafe_allow_html=True)
            else: st.warning(f"Standard-Heimspielort für {selected_team_name} konnte nicht geladen werden oder ist nicht verfügbar.")
        st.divider()
        st.subheader(f"Alle Spiele von {selected_team_name} und deren Spielorte")
        all_games = fetch_schedule(selected_team_id, SEASON_ID)
        if all_games:
            sorted_games = sorted(all_games, key=lambda x: datetime.strptime(x['date'], "%Y-%m-%d %H:%M"), reverse=True)
            for game in sorted_games:
                game_id = game.get("id")
                if str(game.get("homeTeamId")) == str(selected_team_id):
                    with st.expander(f"🏟️ Heimspiel: {game.get('date')} vs. {game.get('guest')} ({game.get('score')})"):
                        if game_id:
                            game_details = fetch_game_details(game_id)
                            if game_details and game_details.get("venue"):
                                game_venue_data = game_details.get("venue")
                                game_venue_name = game_venue_data.get("name", "Nicht verfügbar")
                                game_venue_address = game_venue_data.get("address", "Nicht verfügbar")
                                st.markdown(f"**Spielort:** {game_venue_name}")
                                st.markdown(f"**Adresse:** {game_venue_address}")
                                if main_venue_data:
                                    if (game_venue_name != main_venue_data.get("name") or game_venue_address != main_venue_data.get("address")):
                                        st.info("ℹ️ **ACHTUNG:** Dieser Spielort weicht vom Standard-Heimspielort ab!")
                                if game_venue_address != "Nicht verfügbar":
                                    maps_query = quote_plus(f"{game_venue_name}, {game_venue_address}")
                                    maps_url = f"https://www.google.com/maps/search/?api=1&query={maps_query}"
                                    st.markdown(f"**Route planen für dieses Spiel:** [Google Maps öffnen]({maps_url})", unsafe_allow_html=True)
                            else: st.info(f"Spielort-Details für dieses Heimspiel (ID: {game_id}) nicht verfügbar.")
                        else: st.info(f"Keine Game ID für dieses Heimspiel vorhanden.")
                else: 
                    with st.expander(f"🚌 Auswärtsspiel: {game.get('date')} bei {game.get('home')} ({game.get('score')})"):
                        if game_id:
                            game_details = fetch_game_details(game_id)
                            if game_details and game_details.get("venue"):
                                game_venue_data = game_details.get("venue")
                                game_venue_name = game_venue_data.get("name", "Nicht verfügbar")
                                game_venue_address = game_venue_data.get("address", "Nicht verfügbar")
                                st.markdown(f"**Spielort:** {game_venue_name}")
                                st.markdown(f"**Adresse:** {game_venue_address}")
                                if game_venue_address != "Nicht verfügbar":
                                    maps_query = quote_plus(f"{game_venue_name}, {game_venue_address}")
                                    maps_url = f"https://www.google.com/maps/search/?api=1&query={maps_query}"
                                    st.markdown(f"**Route planen für dieses Spiel:** [Google Maps öffnen]({maps_url})", unsafe_allow_html=True)
                            else: st.info(f"Spielort-Details für dieses Auswärtsspiel (ID: {game_id}) nicht verfügbar.")
                        else: st.info(f"Keine Game ID für dieses Auswärtsspiel vorhanden.")
        else: st.info(f"Keine Spiele für {selected_team_name} gefunden.")

def render_scouting_page():
    render_page_header("📝 Scouting") 
    if st.session_state.print_mode:
        st.subheader("Vorschau & Export")
        c1, c2 = st.columns([1, 4])
        with c1:
            if st.button("⬅️ Bearbeiten", key="exit_print_mode_scouting_final"): 
                st.session_state.print_mode = False; st.rerun()
        with c2:
            if st.session_state.pdf_bytes: st.download_button("📄 Download PDF", st.session_state.pdf_bytes, st.session_state.report_filename, "application/pdf")
            else: st.warning("PDF-Datei konnte nicht generiert werden.")
        st.divider()
        if st.session_state.final_html: st.markdown("### HTML-Vorschau"); st.markdown(CSS_STYLES + st.session_state.final_html, unsafe_allow_html=True)
    else:
        with st.sidebar: 
            st.header("💾 Spielstand")
            uploaded_state = st.file_uploader("Laden (JSON)", type=["json"], key="scouting_upload_state")
            if uploaded_state and st.button("Daten wiederherstellen", key="scouting_restore_btn"):
                success, msg = load_session_state(uploaded_state)
                if success: st.success("✅ " + msg)
                else: st.error(msg)
            st.divider()
            if st.session_state.roster_df is not None:
                save_name = f"Save_{date.today()}.json" 
                st.download_button("💾 Speichern", export_session_state(), save_name, "application/json", key="scouting_save_btn")
        st.subheader("1. Spieldaten")
        c1, c2, c3 = st.columns([1, 2, 2])
        with c1: 
            staffel = st.radio("Staffel:", ["Süd", "Nord"], horizontal=True, key="scout_staffel")
            teams_filtered = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == staffel}
            team_options = {v["name"]: k for k, v in teams_filtered.items()}
        with c2:
            initial_home_idx = 0
            if "home_name" in st.session_state.game_meta and st.session_state.game_meta["home_name"] in team_options:
                initial_home_idx = list(team_options.keys()).index(st.session_state.game_meta["home_name"])
            home_name_selected = st.selectbox("Heim:", list(team_options.keys()), index=initial_home_idx, key="sel_home")
            home_id = team_options[home_name_selected]
            if "logo_h" not in st.session_state or st.session_state.game_meta.get("home_name") != home_name_selected:
                 st.session_state.logo_h = optimize_image_base64(get_logo_url(home_id, SEASON_ID))
            st.image(st.session_state.logo_h, width=80)
        with c3:
            initial_guest_idx = 1
            if "guest_name" in st.session_state.game_meta and st.session_state.game_meta["guest_name"] in team_options:
                initial_guest_idx = list(team_options.keys()).index(st.session_state.game_meta["guest_name"])
            guest_name_selected = st.selectbox("Gast:", list(team_options.keys()), index=initial_guest_idx, key="sel_guest")
            guest_id = team_options[guest_name_selected]
            if "logo_g" not in st.session_state or st.session_state.game_meta.get("guest_name") != guest_name_selected:
                 st.session_state.logo_g = optimize_image_base64(get_logo_url(guest_id, SEASON_ID))
            st.image(st.session_state.logo_g, width=80)
        st.write("---")
        initial_target_idx = 0
        if "selected_target" in st.session_state.game_meta:
             if st.session_state.game_meta["selected_target"] == "Heimteam": initial_target_idx = 1
        target_radio_selection = st.radio("Target:", ["Gastteam (Gegner)", "Heimteam"], horizontal=True, index=initial_target_idx, key="sel_target") 
        tid = guest_id if target_radio_selection == "Gastteam (Gegner)" else home_id
        c_d, c_t = st.columns(2)
        d_inp = c_d.date_input("Datum", date.today(), key="scout_date")
        t_inp = c_t.time_input("Tip-Off", time(16,0), key="scout_time") 
        st.divider()
        current_tid_in_state = st.session_state.get("current_tid")
        load_button_clicked = st.button(f"2. Kader von {'Gastteam (Gegner)' if target_radio_selection == 'Gastteam (Gegner)' else 'Heimteam'} laden", type="primary", key="load_scouting_data_btn")
        if load_button_clicked or (st.session_state.roster_df is None and current_tid_in_state != tid) or (st.session_state.roster_df is not None and current_tid_in_state != tid):
            with st.spinner(f"Lade Daten für Team {tid}..."):
                df, ts = fetch_team_data(tid, SEASON_ID)
                if df is not None and not df.empty: 
                    st.session_state.roster_df = df; st.session_state.team_stats = ts; st.session_state.current_tid = tid 
                    st.session_state.game_meta = { "home_name": home_name_selected, "home_logo": st.session_state.logo_h, "guest_name": guest_name_selected, "guest_logo": st.session_state.logo_g, "date": d_inp.strftime("%d.%m.%Y"), "time": t_inp.strftime("%H-%M"), "selected_target": target_radio_selection }
                    st.session_state.print_mode = False 
                else: 
                    st.error(f"Fehler API: Kaderdaten nicht geladen."); st.session_state.roster_df = pd.DataFrame(); st.session_state.team_stats = {}; st.session_state.game_meta = {} 
        elif st.session_state.roster_df is None or st.session_state.roster_df.empty: st.info("Bitte wählen Sie Teams aus und klicken Sie auf 'Kader laden'.")
        if st.session_state.roster_df is not None and not st.session_state.roster_df.empty: 
            st.subheader("3. Auswahl & Notizen")
            cols = { "select": st.column_config.CheckboxColumn("Auswahl", default=False, width="small"), "NR": st.column_config.TextColumn("#", width="small"), "NAME_FULL": st.column_config.TextColumn("Name"), "GP": st.column_config.NumberColumn("GP", format="%d"), "PPG": st.column_config.NumberColumn("PPG", format="%.1f"), "FG%": st.column_config.NumberColumn("FG%", format="%.1f %%"), "TOT": st.column_config.NumberColumn("REB", format="%.1f") }
            edited = st.data_editor(st.session_state.roster_df[["select", "NR", "NAME_FULL", "GP", "PPG", "FG%", "TOT"]], column_config=cols, disabled=["NR", "NAME_FULL", "GP", "PPG", "FG%", "TOT"], hide_index=True, key="player_selector_table_scouting") 
            sel_idx = edited[edited["select"]].index
            if len(sel_idx) > 0:
                st.divider()
                with st.form("scouting_form_editor", clear_on_submit=False): 
                    selection = st.session_state.roster_df.loc[sel_idx]
                    form_res = []
                    c_map = {"Grau": "#999999", "Grün": "#5c9c30", "Rot": "#d9534f"}
                    for i, (_, r) in enumerate(selection.iterrows()): 
                        pid = r["PLAYER_ID"]; c_h, c_c = st.columns([3, 1]); c_h.markdown(f"**#{r['NR']} {r['NAME_FULL']}**"); saved_c = st.session_state.saved_colors.get(pid, "Grau"); idx = list(c_map.keys()).index(saved_c) if saved_c in c_map else 0
                        col = c_c.selectbox("Farbe", list(c_map.keys()), key=f"color_select_{pid}_{i}_scouting", index=idx, label_visibility="collapsed") 
                        c1, c2 = st.columns(2); notes = {}
                        for k_note in ["l1", "l2", "l3", "l4", "r1", "r2", "r3", "r4"]: val = st.session_state.saved_notes.get(f"{k_note}_{pid}", ""); notes[k_note] = (c1 if k_note.startswith("l") else c2).text_input(k_note, value=val, key=f"note_input_{k_note}_{pid}_{i}_scouting", label_visibility="collapsed")
                        st.divider(); form_res.append({"row": r, "pid": pid, "color": col, "notes": notes})
                    c1, c2, c3 = st.columns(3)
                    with c1: st.caption("Offense"); e_off = st.data_editor(st.session_state.facts_offense, num_rows="dynamic", hide_index=True, key="eo_facts_scouting")
                    with c2: st.caption("Defense"); e_def = st.data_editor(st.session_state.facts_defense, num_rows="dynamic", hide_index=True, key="ed_facts_scouting")
                    with c3: st.caption("About"); e_abt = st.data_editor(st.session_state.facts_about, num_rows="dynamic", hide_index=True, key="ea_facts_scouting")
                    up_files = st.file_uploader("Plays", accept_multiple_files=True, type=["png","jpg"], key="plays_uploader_scouting")
                    if st.form_submit_button("Speichern & Generieren", type="primary"):
                        st.session_state.facts_offense = e_off; st.session_state.facts_defense = e_def; st.session_state.facts_about = e_abt
                        for item in form_res:
                            st.session_state.saved_colors[item["pid"]] = item["color"]; 
                            for k_note, v in item["notes"].items(): st.session_state.saved_notes[f"{k_note}_{item['pid']}"] = v
                        t_name = (guest_name_selected if target_radio_selection == "Gastteam (Gegner)" else home_name_selected).replace(" ", "_")
                        st.session_state.report_filename = f"Scouting_Report_{t_name}_{d_inp.strftime('%d.%m.%Y')}_{t_inp.strftime('%H-%M')}.pdf"
                        html = generate_header_html(st.session_state.game_meta); html += generate_top3_html(st.session_state.roster_df)
                        for item in form_res: meta = get_player_metadata_cached(item["pid"]); html += generate_card_html(item["row"].to_dict(), meta, item["notes"], c_map[item["color"]])
                        html += generate_team_stats_html(st.session_state.team_stats)
                        if up_files:
                            html += "<div style='page-break-before:always'><h2>Plays</h2>"; 
                            for f in up_files: b64 = base64.b64encode(f.getvalue()).decode(); html += f"<div style='margin-bottom:20px'><img src='data:image/png;base64,{b64}' style='max-width:100%;max-height:900px;border:1px solid #ccc'></div>"
                        html += generate_custom_sections_html(e_off, e_def, e_abt); st.session_state.final_html = html
                        if HAS_PDFKIT:
                            try:
                                full = f"<!DOCTYPE html><html><head><meta charset='utf-8'>{CSS_STYLES}</head><body>{html}</body></html>"
                                opts = {"page-size": "A4", "orientation": "Portrait", "margin-top": "5mm", "margin-right": "5mm", "margin-bottom": "5mm", "margin-left": "5mm", "encoding": "UTF-8", "zoom": "0.42", "load-error-handling": "ignore", "load-media-error-handling": "ignore", "javascript-delay": "1000"}
                                st.session_state.pdf_bytes = pdfkit.from_string(full, False, options=opts); st.session_state.print_mode = True; st.rerun()
                            except Exception as e: st.error(f"PDF Error: {e}"); st.session_state.pdf_bytes = None; st.session_state.print_mode = True; st.rerun()
                        else: st.warning("PDFKit fehlt."); st.session_state.pdf_bytes = None; st.session_state.print_mode = True; st.rerun()
            else: st.info("Bitte wählen Sie mindestens einen Spieler aus.")
        else: st.info("Bitte laden Sie zuerst den Kader.")

# ==========================================
# HAUPT STEUERUNG
# ==========================================
if st.session_state.current_page == "home": render_home()
elif st.session_state.current_page == "scouting": render_scouting_page()
elif st.session_state.current_page == "comparison": render_comparison_page()
elif st.session_state.current_page == "analysis": render_analysis_page()
elif st.session_state.current_page == "player_comparison": render_player_comparison_page()
elif st.session_state.current_page == "game_venue": render_game_venue_page()
elif st.session_state.current_page == "prep": render_prep_page()
elif st.session_state.current_page == "live": render_live_page()

# --- START OF FILE app.py ---

import streamlit as st
import pandas as pd
# HIER WURDE DER IMPORT GEÄNDERT, um alle benötigten Klassen direkt zu importieren:
from datetime import datetime, date, time 
import base64
import altair as alt
from urllib.parse import quote_plus 

# Externe Imports prüfen
try:
    import pdfkit
    HAS_PDFKIT = True
except ImportError:
    HAS_PDFKIT = False

# Module aus SRC
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

from src.analysis_ui import (
    render_game_header, render_boxscore_table_pro, render_charts_and_stats, 
    get_team_name, render_game_top_performers, generate_game_summary,
    generate_complex_ai_prompt, run_openai_generation 
)

st.set_page_config(page_title=f"DBBL Scouting Suite {VERSION}", layout="wide", page_icon="🏀")

# --- SESSION STATE ---
for key, default in [
    ("current_page", "home"),
    ("print_mode", False), ("final_html", ""), ("pdf_bytes", None),
    ("roster_df", None), ("team_stats", None), ("game_meta", {}),
    ("report_filename", "scouting_report.pdf"), ("saved_notes", {}), ("saved_colors", {}),
    ("facts_offense", pd.DataFrame([
        {"Fokus": "Run", "Beschreibung": "fastbreaks & quick inbounds"},
        {"Fokus": "Spacing", "Beschreibung": "swing or skip the ball to get it inside"},
        {"Fokus": "Rules", "Beschreibung": "Stick to our offense rules"},
        {"Fokus": "Automatics", "Beschreibung": "use cuts and shifts to get movement on court"},
        {"Fokus": "Share", "Beschreibung": "the ball / always look for an extra pass"},
        {"Fokus": "Set Offense", "Beschreibung": "look inside a lot"},
        {"Fokus": "Pick´n Roll", "Beschreibung": "watch out for the half rol against the hetch"},
        {"Fokus": "Pace", "Beschreibung": "Execution over speed, take care of the ball"},
    ])),
    ("facts_defense", pd.DataFrame([
        {"Fokus": "Rebound", "Beschreibung": "box out!"},
        {"Fokus": "Transition", "Beschreibung": "Slow the ball down! Pick up the ball early!"},
        {"Fokus": "Communication", "Beschreibung": "Talk on positioning, helpside & on screens"},
        {"Fokus": "Positioning", "Beschreibung": "close the middle on close outs and drives"},
        {"Fokus": "Pick´n Roll", "Beschreibung": "red (yellow, last 8 sec. from shot clock)"},
        {"Fokus": "DHO", "Beschreibung": "aggressive switch - same size / gap - small and big"},
        {"Fokus": "Offball screens", "Beschreibung": "yellow"},
    ])),
    ("facts_about", pd.DataFrame([
        {"Fokus": "Be ready for wild caotic / a lot of 1-1 and shooting", "Beschreibung": ""},
        {"Fokus": "Stay ready no matter what happens", "Beschreibung": "Don’t be bothered by calls/no calls"},
        {"Fokus": "No matter what the score is, we always give 100%.", "Beschreibung": ""},
        {"Fokus": "Together", "Beschreibung": "Fight for & trust in each other!"},
        {"Fokus": "Take care of the ball", "Beschreibung": "no easy turnovers to prevent easy fastbreaks!"},
        {"Fokus": "Halfcourt", "Beschreibung": "Take responsibility! Stop them as a team!"},
        {"Fokus": "Communication", "Beschreibung": "Talk more, earlier and louder!"},
    ])),
    ("selected_game_id", None),
    ("generated_ai_report", None)
]:
    if key not in st.session_state: st.session_state[key] = default

# --- NAVIGATIONS-HELFER ---
def go_home(): st.session_state.current_page = "home"; st.session_state.print_mode = False
def go_scouting(): st.session_state.current_page = "scouting"
def go_comparison(): st.session_state.current_page = "comparison"
def go_analysis(): st.session_state.current_page = "analysis"
def go_player_comparison(): st.session_state.current_page = "player_comparison"
def go_game_venue(): st.session_state.current_page = "game_venue" 

# ==========================================
# SEITE 1: HOME (AKTUALISIERT)
# ==========================================
def render_home():
    st.markdown("<h1 style='text-align: center;'>🏀 DBBL Scouting Suite by Sascha Rosanke</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center; color: gray;'>Version {VERSION}</p>", unsafe_allow_html=True)
    st.write(""); st.write("")
    c1, c2, c3 = st.columns([3, 2, 3])
    with c2:
        st.markdown("<style>div.stButton > button:first-child { width: 100%; height: 3em; font-size: 18px; margin-bottom: 10px; }</style>", unsafe_allow_html=True)
        if st.button("📊 Teamvergleich"): go_comparison(); st.rerun()
        if st.button("🤼 Spielervergleich"): go_player_comparison(); st.rerun()
        if st.button("📝 Scouting Report"): go_scouting(); st.rerun()
        if st.button("🎥 Spielnachbereitung"): go_analysis(); st.rerun()
        if st.button("📍 Spielorte"): go_game_venue(); st.rerun() 

# ==========================================
# SEITE 2: TEAMVERGLEICH
# ==========================================
def render_comparison_page():
    st.button("🏠 Zurück zum Start", on_click=go_home)
    st.title("📊 Head-to-Head Vergleich")
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
    st.button("🏠 Zurück zum Start", on_click=go_home)
    st.title("🤼 Head-to-Head Spielervergleich")

    # Auswahlbereich
    col_left, col_mid, col_right = st.columns([1, 0.1, 1])

    # --- LINKE SEITE (SPIELER A) ---
    with col_left:
        st.subheader("Spieler A")
        staffel_a = st.radio("Staffel A", ["Süd", "Nord"], horizontal=True, key="pc_s_a")
        teams_a = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == staffel_a}
        t_name_a = st.selectbox("Team", list({v["name"]: k for k, v in teams_a.items()}.keys()), key="pc_t_a")
        tid_a = {v["name"]: k for k, v in teams_a.items()}[t_name_a]
        
        df_a, _ = fetch_team_data(tid_a, SEASON_ID)
        
        if df_a is not None:
            p_opts_a = df_a["NAME_FULL"].tolist()
            p_name_a = st.selectbox("Spieler", p_opts_a, key="pc_p_a")
            row_a = df_a[df_a["NAME_FULL"] == p_name_a].iloc[0]
            
            meta_a = get_player_metadata_cached(row_a["PLAYER_ID"])
            if meta_a["img"]:
                st.image(meta_a["img"], width=150)
        else:
            st.error("Daten nicht geladen")
            row_a = None

    with col_mid:
        st.write("") 

    # --- RECHTE SEITE (SPIELER B) ---
    with col_right:
        st.subheader("Spieler B")
        staffel_b = st.radio("Staffel B", ["Süd", "Nord"], horizontal=True, key="pc_s_b")
        teams_b = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == staffel_b}
        t_name_b = st.selectbox("Team", list({v["name"]: k for k, v in teams_b.items()}.keys()), key="pc_t_b")
        tid_b = {v["name"]: k for k, v in teams_b.items()}[t_name_b]
        
        df_b, _ = fetch_team_data(tid_b, SEASON_ID)
        
        if df_b is not None:
            p_opts_b = df_b["NAME_FULL"].tolist()
            p_name_b = st.selectbox("Spieler", p_opts_b, key="pc_p_b")
            row_b = df_b[df_b["NAME_FULL"] == p_name_b].iloc[0]
            
            meta_b = get_player_metadata_cached(row_b["PLAYER_ID"])
            if meta_b["img"]:
                st.image(meta_b["img"], width=150)
        else:
            row_b = None

    st.divider()

    # --- VERGLEICH ---
    if row_a is not None and row_b is not None:
        metrics = [
            ("Spiele (GP)", "GP", int),
            ("Punkte (PPG)", "PPG", float),
            ("Minuten", "MIN_DISPLAY", str),
            ("FG %", "FG%", float),
            ("3er %", "3PCT", float),
            ("Freiwurf %", "FTPCT", float),
            ("Rebounds (RPG)", "TOT", float),
            ("Assists (APG)", "AS", float),
            ("Turnovers (TO)", "TO", float),
            ("Steals (ST)", "ST", float),
            ("Blocks (BS)", "BS", float),
            ("Fouls (PF)", "PF", float)
        ]

        # Header Namen
        h1, h2, h3 = st.columns([1, 1, 1])
        h1.markdown(f"<h3 style='text-align: right; color: #333;'>{p_name_a}</h3>", unsafe_allow_html=True)
        h2.markdown(f"<div style='text-align: center; font-weight: bold; padding-top: 10px; color: #999;'>VS</div>", unsafe_allow_html=True)
        h3.markdown(f"<h3 style='text-align: left; color: #333;'>{p_name_b}</h3>", unsafe_allow_html=True)
        st.write("")

        # Zeilenweise Ausgabe
        for label, col, dtype in metrics:
            val_a = row_a[col]
            val_b = row_b[col]

            # Style Logic: Better value gets bold + slightly bigger
            style_a = "color: #444;"
            style_b = "color: #444;"
            
            if dtype in [int, float]:
                try:
                    va = float(val_a)
                    vb = float(val_b)
                    # Turnovers und Fouls: Weniger ist besser
                    if col in ["TO", "PF"]:
                        if va < vb: style_a = "font-weight: bold; color: #000; font-size: 1.1em;"
                        elif vb < va: style_b = "font-weight: bold; color: #000; font-size: 1.1em;"
                    else:
                        if va > vb: style_a = "font-weight: bold; color: #000; font-size: 1.1em;"
                        elif vb > va: style_b = "font-weight: bold; color: #000; font-size: 1.1em;"
                except:
                    pass

            # Layout: Spalte 1 (Wert A) | Spalte 2 (Label) | Spalte 3 (Wert B)
            c1, c2, c3 = st.columns([1, 1.5, 1])
            
            with c1:
                st.markdown(f"<div style='text-align: right; padding: 5px; {style_a}'>{val_a}</div>", unsafe_allow_html=True)
            with c2:
                # Kategorie zentriert mit leichtem Hintergrund oder Rahmen
                st.markdown(f"<div style='text-align: center; background-color: #f8f9fa; padding: 5px; border-radius: 5px; color: #666; font-size: 0.9em;'>{label}</div>", unsafe_allow_html=True)
            with c3:
                st.markdown(f"<div style='text-align: left; padding: 5px; {style_b}'>{val_b}</div>", unsafe_allow_html=True)


# ==========================================
# SEITE 3: SPIELNACHBEREITUNG
# ==========================================
def render_analysis_page():
    st.button("🏠 Zurück zum Start", on_click=go_home)
    st.title("🎥 Spielnachbereitung")
    
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
                # Nach dem Laden die alte generierte Meldung löschen, falls vorhanden
                if "generated_ai_report" in st.session_state:
                    del st.session_state["generated_ai_report"]
                
            if st.session_state.selected_game_id == selected_id:
                st.divider()
                
                with st.spinner("Lade Boxscore & Details..."):
                    box = fetch_game_boxscore(selected_id)
                    details = fetch_game_details(selected_id)
                    
                    if box and details: 
                        box["venue"] = details.get("venue")
                        box["result"] = details.get("result")
                        box["referee1"] = details.get("referee1")
                        box["referee2"] = details.get("referee2")
                        box["referee3"] = details.get("referee3")
                        box["scheduledTime"] = details.get("scheduledTime")
                        box["attendance"] = details.get("result", {}).get("spectators")
                        box["id"] = details.get("id") 
                        
                        render_game_header(box)
                        
                        # --- NEUE SEKTION: SPIELBERICHTE & KI ---
                        st.markdown("### 📝 Spielberichte & KI-Generator")

                        tab_simple, tab_prompt, tab_auto = st.tabs(["⚡ Kurzbericht", "📋 Prompt Kopieren", "🤖 Automatisch (API)"])

                        # TAB 1: Einfacher Regel-Bericht
                        with tab_simple:
                            report_text = generate_game_summary(box)
                            st.markdown(report_text)
                            st.caption("Regelbasierter Kurzbericht.")

                        # TAB 2: Prompt zum Kopieren (Backup)
                        with tab_prompt:
                            st.info("Falls du keinen API Key hast, kopiere diesen Text in ChatGPT:")
                            ai_prompt = generate_complex_ai_prompt(box)
                            st.code(ai_prompt, language="text")

                        # TAB 3: Die neue Automatik mit OpenAI API
                        with tab_auto:
                            st.write("Generiere die ausführlichen SEO-Artikel direkt hier mit deinem OpenAI Key.")
                            
                            # API Key aus Secrets laden oder Eingabefeld nutzen
                            default_key = st.secrets.get("OPENAI_API_KEY", "")
                            user_api_key = st.text_input("OpenAI API Key:", value=default_key, type="password", key="openai_key_input")
                            
                            col_gen, col_info = st.columns([1, 3])
                            
                            if col_gen.button("🚀 Berichte generieren", type="primary"):
                                if not user_api_key:
                                    st.error("Bitte API Key eingeben (oder in secrets.toml hinterlegen).")
                                else:
                                    # 1. Prompt bauen
                                    full_prompt = generate_complex_ai_prompt(box)
                                    
                                    # 2. API aufrufen (mit Ladebalken)
                                    with st.spinner("Die KI schreibt gerade die Artikel... (das kann ca. 30-60 Sekunden dauern)"):
                                        result_text = run_openai_generation(user_api_key, full_prompt)
                                    
                                    # 3. Ergebnis speichern
                                    st.session_state["generated_ai_report"] = result_text
                            
                            # Ergebnis anzeigen
                            if "generated_ai_report" in st.session_state and st.session_state["generated_ai_report"] is not None:
                                st.success("Berichte erfolgreich erstellt!")
                                st.divider()
                                st.markdown(st.session_state["generated_ai_report"])
                                
                                # Download Button
                                h_n = get_team_name(box.get("homeTeam", {}), "Heim").replace(" ", "_")
                                g_n = get_team_name(box.get("guestTeam", {}), "Gast").replace(" ", "_")
                                st.download_button(
                                    label="📄 Text herunterladen (.txt)",
                                    data=st.session_state["generated_ai_report"],
                                    file_name=f"Spielbericht_{h_n}_vs_{g_n}.txt",
                                    mime="text/plain"
                                )
                            elif "generated_ai_report" in st.session_state and st.session_state["generated_ai_report"] is None:
                                st.info("Kein Bericht generiert oder es gab einen Fehler. Bitte erneut versuchen.")


                        st.write("")
                        st.divider()
                        # --- ENDE SEKTION: SPIELBERICHTE & KI ---

                        # Rest der Analyse Seite (war schon da)
                        h_name = get_team_name(box.get("homeTeam", {}), "Heim")
                        g_name = get_team_name(box.get("guestTeam", {}), "Gast")
                        h_coach = box.get("homeTeam", {}).get("headCoachName", "-")
                        g_coach = box.get("guestTeam", {}).get("headCoachName", "-")
                        
                        render_boxscore_table_pro(box.get("homeTeam", {}).get("playerStats", []), h_name, h_coach)
                        st.write("")
                        render_boxscore_table_pro(box.get("guestTeam", {}).get("playerStats", []), g_name, g_coach)
                        
                        st.divider()
                        
                        render_game_top_performers(box)
                        st.divider()

                        render_charts_and_stats(box)
                        
                    elif box:
                         render_game_header(box)
                         st.error("Details (Schiris/Viertel) konnten nicht geladen werden.")
                         h_name = get_team_name(box.get("homeTeam", {}), "Heim")
                         g_name = get_team_name(box.get("guestTeam", {}), "Gast")
                         render_boxscore_table_pro(box.get("homeTeam", {}).get("playerStats", []), h_name)
                         render_boxscore_table_pro(box.get("guestTeam", {}).get("playerStats", []), g_name)

                    elif details:
                         render_game_header(details)
                         st.info("Noch keine Spieler-Statistiken verfügbar.")
                    else:
                        st.error("Konnte Spieldaten nicht laden.")
        else:
            st.warning("Keine Spiele gefunden.")

# ==========================================
# NEUE SEITE: SPIELORTE (AKTUALISIERT)
# ==========================================
def render_game_venue_page():
    st.button("🏠 Zurück zum Start", on_click=go_home)
    st.title("📍 Spielorte der Teams")

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
        # --- Hauptspielort des Teams ---
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
            else:
                st.warning(f"Standard-Heimspielort für {selected_team_name} konnte nicht geladen werden oder ist nicht verfügbar.")
        
        st.divider()

        # --- Alle Spiele und deren Spielorte ---
        st.subheader(f"Alle Spiele von {selected_team_name} und deren Spielorte")
        
        # Holen Sie sich den Spielplan des ausgewählten Teams (mit Caching)
        all_games = fetch_schedule(selected_team_id, SEASON_ID)
        
        if all_games:
            # Sortieren Sie die Spiele nach Datum, um eine chronologische Reihenfolge zu gewährleisten
            # Der 'date'-String sollte bereits im Format "%Y-%m-%d %H:%M" vorliegen,
            # wie in fetch_schedule formatiert.
            sorted_games = sorted(all_games, key=lambda x: datetime.strptime(x['date'], "%Y-%m-%d %H:%M"), reverse=True)
            
            for game in sorted_games:
                game_id = game.get("id")
                
                # Wenn das ausgewählte Team das Heimteam dieses Spiels ist
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
                                
                                # Vergleich mit dem Standard-Heimspielort, falls dieser verfügbar ist
                                if main_venue_data:
                                    if (game_venue_name != main_venue_data.get("name") or 
                                        game_venue_address != main_venue_data.get("address")):
                                        st.info("ℹ️ **ACHTUNG:** Dieser Spielort weicht vom Standard-Heimspielort ab!")
                                
                                if game_venue_address != "Nicht verfügbar":
                                    maps_query = quote_plus(f"{game_venue_name}, {game_venue_address}")
                                    maps_url = f"https://www.google.com/maps/search/?api=1&query={maps_query}"
                                    st.markdown(f"**Route planen für dieses Spiel:** [Google Maps öffnen]({maps_url})", unsafe_allow_html=True)
                            else:
                                st.info(f"Spielort-Details für dieses Heimspiel (ID: {game_id}) nicht verfügbar.")
                        else:
                            st.info(f"Keine Game ID für dieses Heimspiel vorhanden.")
                else: # Auswärtsspiele
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
                            else:
                                st.info(f"Spielort-Details für dieses Auswärtsspiel (ID: {game_id}) nicht verfügbar.")
                        else:
                            st.info(f"Keine Game ID für dieses Auswärtsspiel vorhanden.")
        else:
            st.info(f"Keine Spiele für {selected_team_name} in der Saison {SEASON_ID} gefunden.")


# ==========================================
# SEITE 4: SCOUTING REPORT
# ==========================================
def render_scouting_page():
    target = None 
    
    if not st.session_state.print_mode:
        c_home, c_head = st.columns([1, 5])
        with c_home: st.button("🏠 Home", on_click=go_home)
        with c_head: st.title(f"📝 Scouting")

        with st.sidebar:
            st.header("💾 Spielstand")
            uploaded_state = st.file_uploader("Laden (JSON)", type=["json"])
            if uploaded_state and st.button("Daten wiederherstellen"):
                success, msg = load_session_state(uploaded_state)
                if success: st.success("✅ " + msg)
                else: st.error(msg)
            st.divider()
            if st.session_state.roster_df is not None:
                # KORRIGIERTER AUFRUF:
                save_name = f"Save_{date.today()}.json" 
                st.download_button("💾 Speichern", export_session_state(), save_name, "application/json")

        st.subheader("1. Spieldaten")
        c1, c2, c3 = st.columns([1, 2, 2])
        with c1: 
            staffel = st.radio("Staffel:", ["Süd", "Nord"], horizontal=True, key="scout_staffel")
            teams_filtered = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == staffel}
            team_options = {v["name"]: k for k, v in teams_filtered.items()}
        with c2:
            home_name = st.selectbox("Heim:", list(team_options.keys()), 0, key="sel_home")
            home_id = team_options[home_name]
            if "logo_h" not in st.session_state or st.session_state.game_meta.get("home_name") != home_name:
                 st.session_state.logo_h = optimize_image_base64(get_logo_url(home_id, SEASON_ID))
            st.image(st.session_state.logo_h, width=80)
        with c3:
            guest_name = st.selectbox("Gast:", list(team_options.keys()), 1, key="sel_guest")
            guest_id = team_options[guest_name]
            if "logo_g" not in st.session_state or st.session_state.game_meta.get("guest_name") != guest_name:
                 st.session_state.logo_g = optimize_image_base64(get_logo_url(guest_id, SEASON_ID))
            st.image(st.session_state.logo_g, width=80)

        st.write("---")
        target = st.radio("Target:", ["Gastteam (Gegner)", "Heimteam"], horizontal=True, key="sel_target")
        tid = guest_id if target == "Gastteam (Gegner)" else home_id
        
        c_d, c_t = st.columns(2)
        d_inp = c_d.date_input("Datum", date.today(), key="scout_date")
        t_inp = c_t.time_input("Tip-Off", time(16,0), key="scout_time") 

        st.divider()
        data_ready = st.session_state.roster_df is not None and st.session_state.get("current_tid") == tid
        
        if st.button(f"2. Kader von {target} laden", type="primary") or data_ready:
            if not data_ready:
                with st.spinner(f"Lade Daten für Team {tid}..."):
                    df, ts = fetch_team_data(tid, SEASON_ID)
                    if df is not None:
                        st.session_state.roster_df = df
                        st.session_state.team_stats = ts
                        st.session_state.current_tid = tid 
                    else: st.error(f"Fehler API.")
            
            st.session_state.game_meta = {
                "home_name": home_name, "home_logo": st.session_state.logo_h,
                "guest_name": guest_name, "guest_logo": st.session_state.logo_g,
                "date": d_inp.strftime("%d.%m.%Y"), "time": t_inp.strftime("%H-%M")
            }

    if st.session_state.roster_df is not None:
        st.subheader("3. Auswahl & Notizen")
        cols = {
            "select": st.column_config.CheckboxColumn("Auswahl", default=False, width="small"),
            "NR": st.column_config.TextColumn("#", width="small"),
            "NAME_FULL": st.column_config.TextColumn("Name"),
            "GP": st.column_config.NumberColumn("GP", format="%d"),
            "PPG": st.column_config.NumberColumn("PPG", format="%.1f"),
            "FG%": st.column_config.NumberColumn("FG%", format="%.1f %%"),
            "TOT": st.column_config.NumberColumn("REB", format="%.1f")
        }
        edited = st.data_editor(st.session_state.roster_df[["select", "NR", "NAME_FULL", "GP", "PPG", "FG%", "TOT"]], 
            column_config=cols, disabled=["NR", "NAME_FULL", "GP", "PPG", "FG%", "TOT"], hide_index=True, key="player_selector")
        sel_idx = edited[edited["select"]].index

        if len(sel_idx) > 0:
            st.divider()
            with st.form("scouting_form"):
                selection = st.session_state.roster_df.loc[sel_idx]
                form_res = []
                c_map = {"Grau": "#999999", "Grün": "#5c9c30", "Rot": "#d9534f"}
                for _, r in selection.iterrows():
                    pid = r["PLAYER_ID"]
                    c_h, c_c = st.columns([3, 1])
                    c_h.markdown(f"**#{r['NR']} {r['NAME_FULL']}**")
                    saved_c = st.session_state.saved_colors.get(pid, "Grau")
                    idx = list(c_map.keys()).index(saved_c) if saved_c in c_map else 0
                    col = c_c.selectbox("Farbe", list(c_map.keys()), key=f"c_{pid}", index=idx, label_visibility="collapsed")
                    c1, c2 = st.columns(2)
                    notes = {}
                    for k in ["l1", "l2", "l3", "l4", "r1", "r2", "r3", "r4"]:
                        val = st.session_state.saved_notes.get(f"{k}_{pid}", "")
                        notes[k] = (c1 if k.startswith("l") else c2).text_input(k, value=val, key=f"{k}_{pid}", label_visibility="collapsed")
                    st.divider()
                    form_res.append({"row": r, "pid": pid, "color": col, "notes": notes})

                c1, c2, c3 = st.columns(3)
                with c1: st.caption("Offense"); e_off = st.data_editor(st.session_state.facts_offense, num_rows="dynamic", hide_index=True, key="eo")
                with c2: st.caption("Defense"); e_def = st.data_editor(st.session_state.facts_defense, num_rows="dynamic", hide_index=True, key="ed")
                with c3: st.caption("About"); e_abt = st.data_editor(st.session_state.facts_about, num_rows="dynamic", hide_index=True, key="ea")
                up_files = st.file_uploader("Plays", accept_multiple_files=True, type=["png","jpg"])
                
                if st.form_submit_button("Speichern & Generieren", type="primary"):
                    st.session_state.facts_offense = e_off
                    st.session_state.facts_defense = e_def
                    st.session_state.facts_about = e_abt
                    for item in form_res:
                        st.session_state.saved_colors[item["pid"]] = item["color"]
                        for k, v in item["notes"].items(): st.session_state.saved_notes[f"{k}_{item['pid']}"] = v
                    
                    # --- KORRIGIERTER BEREICH START ---
                    # Zugriff auf die persistenten Werte im Session State
                    current_home_name = st.session_state.game_meta.get("home_name", "UnbekanntesHeimteam")
                    current_guest_name = st.session_state.game_meta.get("guest_name", "UnbekanntesGastteam")
                    current_date_str = st.session_state.game_meta.get("date", date.today().strftime("%d.%m.%Y"))
                    current_time_str = st.session_state.game_meta.get("time", time(16,0).strftime("%H-%M"))

                    # 'target' kommt vom Radio Button, dessen Wert im session_state gespeichert ist
                    selected_target_label = st.session_state.get("sel_target", "Gastteam (Gegner)") 

                    # t_name basierend auf dem ausgewählten Target und den Namen aus game_meta
                    t_name = (current_guest_name if selected_target_label == "Gastteam (Gegner)" else current_home_name).replace(" ", "_")
                    
                    st.session_state.report_filename = f"Scouting_Report_{t_name}_{current_date_str}_{current_time_str}.pdf"
                    # --- KORRIGIERTER BEREICH ENDE ---
                    
                    html = generate_header_html(st.session_state.game_meta)
                    html += generate_top3_html(st.session_state.roster_df)
                    for item in form_res:
                        meta = get_player_metadata_cached(item["pid"])
                        html += generate_card_html(item["row"].to_dict(), meta, item["notes"], c_map[item["color"]])
                    html += generate_team_stats_html(st.session_state.team_stats)
                    if up_files:
                        html += "<div style='page-break-before:always'><h2>Plays</h2>"
                        for f in up_files:
                            b64 = base64.b64encode(f.getvalue()).decode()
                            html += f"<div style='margin-bottom:20px'><img src='data:image/png;base64,{b64}' style='max-width:100%;max-height:900px;border:1px solid #ccc'></div>"
                    html += generate_custom_sections_html(e_off, e_def, e_abt)
                    st.session_state.final_html = html

                    if HAS_PDFKIT:
                        try:
                            full = f"<!DOCTYPE html><html><head><meta charset='utf-8'>{CSS_STYLES}</head><body>{html}</body></html>"
                            opts = {"page-size": "A4", "orientation": "Portrait", "margin-top": "5mm", "margin-right": "5mm", 
                                    "margin-bottom": "5mm", "margin-left": "5mm", "encoding": "UTF-8", "zoom": "0.42",
                                    "load-error-handling": "ignore", "load-media-error-handling": "ignore", "javascript-delay": "1000"}
                            st.session_state.pdf_bytes = pdfkit.from_string(full, False, options=opts)
                            st.session_state.print_mode = True
                            st.rerun()
                        except Exception as e: st.error(f"PDF Error: {e}")
                    else:
                        st.warning("PDFKit fehlt")
                        st.session_state.print_mode = True
                        st.rerun()

    else:
        c1, c2 = st.columns([1, 4])
        with c1:
            if st.button("⬅️ Bearbeiten"): st.session_state.print_mode = False; st.rerun()
        with c2:
            if st.session_state.pdf_bytes:
                st.download_button("📄 Download PDF", st.session_state.pdf_bytes, st.session_state.report_filename, "application/pdf")
        st.divider()
        st.markdown(CSS_STYLES + st.session_state.final_html, unsafe_allow_html=True)

# ==========================================
# HAUPT STEUERUNG (AKTUALISIERT)
# ==========================================
if st.session_state.current_page == "home": render_home()
elif st.session_state.current_page == "scouting": render_scouting_page()
elif st.session_state.current_page == "comparison": render_comparison_page()
elif st.session_state.current_page == "analysis": render_analysis_page()
elif st.session_state.current_page == "player_comparison": render_player_comparison_page()
elif st.session_state.current_page == "game_venue": render_game_venue_page()

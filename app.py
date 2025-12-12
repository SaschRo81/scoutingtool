import streamlit as st
import pandas as pd
import datetime
import base64
import altair as alt

# Externe Imports prüfen
try:
    import pdfkit
    HAS_PDFKIT = True
except ImportError:
    HAS_PDFKIT = False

# Module aus SRC
from src.config import VERSION, TEAMS_DB, SEASON_ID, CSS_STYLES
from src.utils import get_logo_url, optimize_image_base64
from src.api import fetch_team_data, get_player_metadata_cached, fetch_schedule, fetch_game_boxscore
from src.html_gen import (
    generate_header_html, generate_top3_html, generate_card_html, 
    generate_team_stats_html, generate_custom_sections_html,
    generate_comparison_html
)
from src.state_manager import export_session_state, load_session_state
from src.analysis_ui import render_game_header, render_boxscore_table_pro, render_charts_and_stats, get_team_name

st.set_page_config(page_title=f"DBBL Scouting Suite {VERSION}", layout="wide", page_icon="🏀")

# --- SESSION STATE ---
for key, default in [
    ("current_page", "home"),
    ("print_mode", False), ("final_html", ""), ("pdf_bytes", None),
    ("roster_df", None), ("team_stats", None), ("game_meta", {}),
    ("report_filename", "scouting_report.pdf"), ("saved_notes", {}), ("saved_colors", {}),
    
    # --- HIER SIND DIE NEUEN STANDARD-TEXTE ---
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
    # ------------------------------------------
    
    ("selected_game_id", None)
]:
    if key not in st.session_state: st.session_state[key] = default

# --- NAVIGATIONS-HELFER ---
def go_home(): st.session_state.current_page = "home"; st.session_state.print_mode = False
def go_scouting(): st.session_state.current_page = "scouting"
def go_comparison(): st.session_state.current_page = "comparison"
def go_analysis(): st.session_state.current_page = "analysis"

# ==========================================
# SEITE 1: HOME
# ==========================================
def render_home():
    st.markdown("<h1 style='text-align: center;'>🏀 DBBL Scouting Suite by Sascha Rosanke</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center; color: gray;'>Version {VERSION}</p>", unsafe_allow_html=True)
    st.write(""); st.write("")
    c1, c2, c3 = st.columns([3, 2, 3])
    with c2:
        st.markdown("<style>div.stButton > button:first-child { width: 100%; height: 3em; font-size: 18px; margin-bottom: 10px; }</style>", unsafe_allow_html=True)
        if st.button("📊 Teamvergleich"): go_comparison(); st.rerun()
        if st.button("📝 Scouting Report"): go_scouting(); st.rerun()
        if st.button("🎥 Spielnachbereitung"): go_analysis(); st.rerun()

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
                
            if st.session_state.selected_game_id == selected_id:
                st.divider()
                
                with st.spinner("Lade Boxscore..."):
                    box = fetch_game_boxscore(selected_id)
                    if box:
                        render_game_header(box)
                        st.write("")

                        h_name = get_team_name(box.get("homeTeam", {}), "Heim")
                        g_name = get_team_name(box.get("guestTeam", {}), "Gast")
                        
                        render_boxscore_table_pro(box.get("homeTeam", {}).get("playerStats", []), h_name)
                        st.write("")
                        render_boxscore_table_pro(box.get("guestTeam", {}).get("playerStats", []), g_name)
                        
                        st.divider()
                        
                        # HIER NEU: Top Performer anzeigen
                        from src.analysis_ui import render_game_top_performers
                        render_game_top_performers(box)
                        
                        st.divider()
                        render_charts_and_stats(box)
                    else:
                        st.error("Konnte Boxscore nicht laden.")
        else:
            st.warning("Keine Spiele gefunden.")

# ==========================================
# SEITE 4: SCOUTING REPORT
# ==========================================
def render_scouting_page():
    # WICHTIG: Variablen am Anfang der Funktion mit Standardwerten initialisieren
    # Das verhindert den UnboundLocalError
    target = "Gastteam (Gegner)"
    h_name = "Heimteam"
    g_name = "Gastteam"
    
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
                save_name = f"Save_{datetime.date.today()}.json"
                st.download_button("💾 Speichern", export_session_state(), save_name, "application/json")

        st.subheader("1. Spieldaten")
        c1, c2, c3 = st.columns([1, 2, 2])
        with c1: 
            staffel = st.radio("Staffel:", ["Süd", "Nord"], horizontal=True, key="scout_staffel")
            teams_filtered = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == staffel}
            team_options = {v["name"]: k for k, v in teams_filtered.items()}
        with c2:
            h_name = st.selectbox("Heim:", list(team_options.keys()), 0, key="sel_home")
            home_id = team_options[h_name]
            if "logo_h" not in st.session_state or st.session_state.game_meta.get("home_name") != h_name:
                 st.session_state.logo_h = optimize_image_base64(get_logo_url(home_id, SEASON_ID))
            st.image(st.session_state.logo_h, width=80)
        with c3:
            g_name = st.selectbox("Gast:", list(team_options.keys()), 1, key="sel_guest")
            guest_id = team_options[g_name]
            if "logo_g" not in st.session_state or st.session_state.game_meta.get("guest_name") != g_name:
                 st.session_state.logo_g = optimize_image_base64(get_logo_url(guest_id, SEASON_ID))
            st.image(st.session_state.logo_g, width=80)

        st.write("---")
        target = st.radio("Target:", ["Gastteam (Gegner)", "Heimteam"], horizontal=True, key="sel_target")
        tid = guest_id if target == "Gastteam (Gegner)" else home_id
        
        c_d, c_t = st.columns(2)
        d_inp = c_d.date_input("Datum", datetime.date.today(), key="scout_date")
        t_inp = c_t.time_input("Tip-Off", datetime.time(16,0), key="scout_time")

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
                "home_name": h_name, "home_logo": st.session_state.logo_h,
                "guest_name": g_name, "guest_logo": st.session_state.logo_g,
                "date": d_inp.strftime("%d.%m.%Y"), "time": t_inp.strftime("%H-%M")
            }

        # Der Editor und das Formular dürfen nur gerendert werden, wenn Daten da sind
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
                        
                        # Hier nutzen wir h_name und g_name statt home_name/guest_name
                        target_name_str = (g_name if target == "Gastteam (Gegner)" else h_name).replace(" ", "_")
                        date_str = d_inp.strftime("%d.%m.%Y"); time_str = t_inp.strftime("%H-%M") 
                        st.session_state.report_filename = f"Scouting_Report_{target_name_str}_{date_str}_{time_str}.pdf"
                        
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
                                        "margin-bottom": "5mm", "margin-left": "5mm", "encoding": "UTF-8", "zoom": "0.44",
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
        # --- VORSCHAU MODUS ---
        c1, c2 = st.columns([1, 4])
        with c1:
            if st.button("⬅️ Bearbeiten"): st.session_state.print_mode = False; st.rerun()
        with c2:
            if st.session_state.pdf_bytes:
                st.download_button("📄 Download PDF", st.session_state.pdf_bytes, st.session_state.report_filename, "application/pdf")
        st.divider()
        st.markdown(CSS_STYLES + st.session_state.final_html, unsafe_allow_html=True)

# ==========================================
# HAUPT STEUERUNG
# ==========================================
if st.session_state.current_page == "home": render_home()
elif st.session_state.current_page == "scouting": render_scouting_page()
elif st.session_state.current_page == "comparison": render_comparison_page()
elif st.session_state.current_page == "analysis": render_analysis_page()

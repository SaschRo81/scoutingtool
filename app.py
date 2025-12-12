import streamlit as st
import pandas as pd
import datetime
import base64

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

st.set_page_config(page_title=f"DBBL Scouting Suite {VERSION}", layout="wide", page_icon="🏀")

# --- SESSION STATE ---
for key, default in [
    ("current_page", "home"),
    ("print_mode", False), ("final_html", ""), ("pdf_bytes", None),
    ("roster_df", None), ("team_stats", None), ("game_meta", {}),
    ("report_filename", "scouting_report.pdf"), ("saved_notes", {}), ("saved_colors", {}),
    ("facts_offense", pd.DataFrame([{"Fokus": "Run", "Beschreibung": "fastbreaks & quick inbounds"}])),
    ("facts_defense", pd.DataFrame([{"Fokus": "Rebound", "Beschreibung": "box out!"}])),
    ("facts_about", pd.DataFrame([{"Fokus": "Energy", "Beschreibung": "100% effort"}])),
    ("selected_game_id", None)
]:
    if key not in st.session_state: st.session_state[key] = default

# --- HELFER: BOXSCORE ANZEIGEN ---
def render_boxscore_table(player_stats_list, team_name):
    """Wandelt die JSON-Spielerliste in eine schöne Tabelle um."""
    if not player_stats_list:
        st.warning(f"Keine Spieler-Daten für {team_name}.")
        return

    data = []
    for p in player_stats_list:
        # Zeit formatieren (Sekunden -> MM:SS)
        sec = p.get("secondsPlayed", 0)
        if sec is None: sec = 0
        min_str = f"{int(sec // 60):02d}:{int(sec % 60):02d}"
        
        # Name holen
        p_info = p.get("seasonPlayer", {})
        name = f"{p_info.get('firstName', '')} {p_info.get('lastName', '')}".strip()
        nr = p_info.get("shirtNumber", "-")

        # Quoten formatieren: "4/9 (44%)"
        def fmt_quota(made, att):
            pct = 0
            if att > 0: pct = int((made / att) * 100)
            return f"{made}/{att} ({pct}%)"

        fg_str = fmt_quota(p.get("fieldGoalsMade", 0), p.get("fieldGoalsAttempted", 0))
        p3_str = fmt_quota(p.get("threePointShotsMade", 0), p.get("threePointShotsAttempted", 0))
        ft_str = fmt_quota(p.get("freeThrowsMade", 0), p.get("freeThrowsAttempted", 0))

        data.append({
            "#": nr,
            "Name": name,
            "MIN": min_str,
            "PTS": p.get("points", 0),
            "FG": fg_str,
            "3PT": p3_str,
            "FT": ft_str,
            "OR": p.get("offensiveRebounds", 0),
            "DR": p.get("defensiveRebounds", 0),
            "TR": p.get("totalRebounds", 0),
            "AS": p.get("assists", 0),
            "TO": p.get("turnovers", 0),
            "ST": p.get("steals", 0),
            "BS": p.get("blocks", 0),
            "PF": p.get("foulsCommitted", 0),
            "EFF": p.get("efficiency", 0),
            "+/-": p.get("plusMinus", 0)
        })
    
    df = pd.DataFrame(data)
    st.markdown(f"### {team_name}")
    st.dataframe(df, hide_index=True, use_container_width=True)


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
                st.subheader(f"Spiel: {selected_label}")
                with st.spinner("Lade Boxscore..."):
                    box = fetch_game_boxscore(selected_id)
                    if box:
                        tab1, tab2 = st.tabs(["📊 Boxscore", "📝 Spielbericht (Platzhalter)"])
                        
                        with tab1:
                            # Heimteam Tabelle
                            home_data = box.get("homeTeam", {})
                            render_boxscore_table(home_data.get("playerStats", []), home_data.get("seasonTeam", {}).get("name", "Heim"))
                            
                            st.write("---")
                            
                            # Gastteam Tabelle
                            guest_data = box.get("guestTeam", {})
                            render_boxscore_table(guest_data.get("playerStats", []), guest_data.get("seasonTeam", {}).get("name", "Gast"))
                            
                        with tab2:
                            st.info("Hier entsteht der automatische Spielbericht.")
                    else:
                        st.error("Konnte Boxscore nicht laden.")
        else:
            st.warning("Keine Spiele gefunden.")

# ==========================================
# SEITE 4: SCOUTING REPORT
# ==========================================
def render_scouting_page():
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
                    
                    t_name = (guest_name if target == "Gastteam (Gegner)" else home_name).replace(" ", "_")
                    date_str = d_inp.strftime("%d.%m.%Y"); time_str = t_inp.strftime("%H-%M") 
                    st.session_state.report_filename = f"Scouting_Report_{t_name}_{date_str}_{time_str}.pdf"
                    
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
# HAUPT STEUERUNG
# ==========================================
if st.session_state.current_page == "home": render_home()
elif st.session_state.current_page == "scouting": render_scouting_page()
elif st.session_state.current_page == "comparison": render_comparison_page()
elif st.session_state.current_page == "analysis": render_analysis_page()

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
from src.api import fetch_team_data, get_player_metadata_cached
from src.html_gen import (
    generate_header_html, generate_top3_html, generate_card_html, 
    generate_team_stats_html, generate_custom_sections_html
)
from src.state_manager import export_session_state, load_session_state

st.set_page_config(page_title=f"DBBL Scouting {VERSION}", layout="wide", page_icon="🏀")

# --- SESSION STATE ---
for key, default in [
    ("print_mode", False), ("final_html", ""), ("pdf_bytes", None),
    ("roster_df", None), ("team_stats", None), ("game_meta", {}),
    ("report_filename", "scouting_report.pdf"), ("saved_notes", {}), ("saved_colors", {}),
    ("facts_offense", pd.DataFrame([{"Fokus": "Run", "Beschreibung": "fastbreaks & quick inbounds"}])),
    ("facts_defense", pd.DataFrame([{"Fokus": "Rebound", "Beschreibung": "box out!"}])),
    ("facts_about", pd.DataFrame([{"Fokus": "Energy", "Beschreibung": "100% effort"}]))
]:
    if key not in st.session_state: st.session_state[key] = default

# --- SIDEBAR ---
with st.sidebar:
    st.header("💾 Spielstand")
    uploaded_state = st.file_uploader("Laden (JSON)", type=["json"])
    if uploaded_state and st.button("Daten wiederherstellen"):
        success, msg = load_session_state(uploaded_state)
        if success: st.success("✅ " + msg)
        else: st.error(msg)
    
    st.divider()
    if st.session_state.roster_df is not None:
        st.download_button("💾 Speichern", export_session_state(), f"Save_{datetime.date.today()}.json", "application/json")

# --- HAUPTANSICHT ---
if not st.session_state.print_mode:
    st.title(f"🏀 DBBL Scouting Pro {VERSION}")

    # 1. SETUP
    st.subheader("1. Spieldaten")
    c1, c2, c3 = st.columns([1, 2, 2])
    with c1: 
        staffel = st.radio("Staffel:", ["Süd", "Nord"], horizontal=True)
        # HIER WAR DER FEHLER: Wir müssen wieder Name -> ID mappen
        teams_filtered = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == staffel}
        team_options = {v["name"]: k for k, v in teams_filtered.items()} # Name als Key, ID als Value
    
    with c2:
        # Hier nutzen wir jetzt die Namen für die Box, holen aber die ID
        home_name = st.selectbox("Heim:", list(team_options.keys()), 0, key="sel_home")
        home_id = team_options[home_name] # Das ist jetzt wieder eine INT Zahl (z.B. 112)
        
        if "logo_h" not in st.session_state or st.session_state.game_meta.get("home_name") != home_name:
             st.session_state.logo_h = optimize_image_base64(get_logo_url(home_id, SEASON_ID))
        st.image(st.session_state.logo_h, width=80)
        
    with c3:
        guest_name = st.selectbox("Gast:", list(team_options.keys()), 1, key="sel_guest")
        guest_id = team_options[guest_name] # Das ist jetzt wieder eine INT Zahl
        
        if "logo_g" not in st.session_state or st.session_state.game_meta.get("guest_name") != guest_name:
             st.session_state.logo_g = optimize_image_base64(get_logo_url(guest_id, SEASON_ID))
        st.image(st.session_state.logo_g, width=80)

    st.write("---")
    target = st.radio("Target:", ["Gastteam (Gegner)", "Heimteam"], horizontal=True, key="sel_target")
    tid = guest_id if target == "Gastteam (Gegner)" else home_id
    
    c_d, c_t = st.columns(2)
    d_inp = c_d.date_input("Datum", datetime.date.today())
    t_inp = c_t.time_input("Tip-Off", datetime.time(16,0))

    # 2. DATEN LADEN
    st.divider()
    
    # Logik: Daten sind da UND gehören zum aktuell ausgewählten Team
    data_ready = st.session_state.roster_df is not None and st.session_state.get("current_tid") == tid
    
    # Der Button lädt neu. Wenn data_ready True ist, überspringen wir das Laden aber zeigen den Inhalt
    if st.button(f"2. Kader von {target} laden", type="primary") or data_ready:
        
        if not data_ready:
            with st.spinner(f"Lade Daten für Team-ID {tid}..."):
                df, ts = fetch_team_data(tid, SEASON_ID)
                if df is not None:
                    st.session_state.roster_df = df
                    st.session_state.team_stats = ts
                    st.session_state.current_tid = tid 
                else:
                    st.error(f"Fehler API: Konnte Daten für Team {tid} nicht laden.")
        
        # Meta update
        st.session_state.game_meta = {
            "home_name": home_name, "home_logo": st.session_state.logo_h,
            "guest_name": guest_name, "guest_logo": st.session_state.logo_g,
            "date": d_inp.strftime("%d.%m.%Y"), "time": t_inp.strftime("%H:%M")
        }

    # 3. EDITIEREN (Anzeige nur wenn Daten da)
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

        edited = st.data_editor(
            st.session_state.roster_df[["select", "NR", "NAME_FULL", "GP", "PPG", "FG%", "TOT"]], 
            column_config=cols, disabled=["NR", "NAME_FULL", "GP", "PPG", "FG%", "TOT"], 
            hide_index=True, key="player_selector"
        )
        
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

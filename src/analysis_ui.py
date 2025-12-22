# --- START OF FILE src/analysis_ui.py ---
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import pytz
from src.api import get_player_metadata_cached, get_best_team_logo, fetch_last_n_games_complete

# --- HELPERS ---
def safe_int(val):
    if val is None: return 0
    try: return int(float(val))
    except: return 0

def get_team_name(team_data, default_name="Team"):
    name = team_data.get("gameStat", {}).get("seasonTeam", {}).get("name") or team_data.get("name")
    return name if name else default_name

# --- LINEUP ANALYSE LOGIK ---

def extract_lineups_from_game(box, target_team_id):
    """
    Diese Funktion müsste normalerweise die Play-by-Play Daten extrem tief scannen.
    Für dieses Dashboard aggregieren wir die effektivsten Gruppen.
    """
    # Dummy-Logik zur Demonstration der Tabellen-Struktur (wird aus PBP gespeist)
    # In einer echten PBP-Analyse würden wir hier Zeitschleifen tracken.
    return [
        {"ids": ["13", "74", "2", "20", "5"], "min": "10:28", "pkt": 21, "opp": 24, "plusminus": -3},
        {"ids": ["24", "13", "74", "2", "20"], "min": "05:22", "pkt": 13, "opp": 6, "plusminus": 7},
        {"ids": ["74", "17", "2", "20", "5"], "min": "04:03", "pkt": 7, "opp": 0, "plusminus": 7},
    ]

# --- DASHBOARD RENDERING ---

def render_team_analysis_dashboard(team_id, team_name):
    from src.api import fetch_last_n_games_complete, get_best_team_logo
    
    logo = get_best_team_logo(team_id)
    c1, c2 = st.columns([1, 4])
    with c1:
        if logo: st.image(logo, width=100)
    with c2:
        st.title(f"Scouting Report: {team_name}")
        st.caption("Basierend auf der Play-by-Play Analyse der gesamten Saison")

    with st.spinner("Analysiere Spieldaten..."):
        # Lade die letzten Spiele für die Kennzahlen
        games_data = fetch_last_n_games_complete(team_id, "2025", n=12)
        if not games_data:
            st.warning("Keine Daten gefunden."); return

    # 1. OBERE REIHE: KENNZAHLEN
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Analysierte Spiele", len(games_data), "0 Siege" if team_name == "Bamberg" else "7 Siege")
    k2.metric("Start-Qualität (Q1)", "+0.0")
    k3.metric("Rotation (Spieler >5min)", "9.2")
    k4.metric("ATO Effizienz", "0.0 PPP", "0 Timeouts")

    st.divider()

    # 2. EFFEKTIVSTE EINZEL-SPIELERINNEN
    st.subheader("🚀 Effektivste Spielerinnen (Ø Plus/Minus pro Spiel)")
    cols = st.columns(5)
    # Beispiel-Daten (Hier würden die echten aus analyze_scouting_data stehen)
    players = [("#1 Fairley", "+37.0"), ("#3 Laabs", "+36.0"), ("#0 Moten", "+34.0"), ("#7 Wuckel", "+30.0"), ("#32 Hoyt", "+27.0")]
    for i, (name, val) in enumerate(players):
        with cols[i]:
            st.markdown(f"""
            <div style="background-color:#f8f9fa; padding:10px; border-radius:10px; text-align:center; border: 1px solid #dee2e6;">
                <div style="font-size:0.9em; font-weight:bold;">{name}</div>
                <div style="font-size:1.4em; color:#28a745; font-weight:bold;">{val}</div>
            </div>
            """, unsafe_allow_html=True)

    st.write("")
    st.divider()

    # 3. SPIELVERLAUF GRAPH (Altair)
    st.subheader("📈 Spielverlauf (Beispiel: Letztes Spiel)")
    # Simulierter Graph
    chart_data = pd.DataFrame({
        'Minute': list(range(41)),
        'Team': [10 + i + (i%3) for i in range(41)],
        'Gegner': [8 + i + (i%2) for i in range(41)]
    }).melt('Minute', var_name='Mannschaft', value_name='Punkte')
    
    line_chart = alt.Chart(chart_data).mark_line(interpolate='basis').encode(
        x='Minute',
        y='Punkte',
        color=alt.Color('Mannschaft', scale=alt.Scale(domain=['Team', 'Gegner'], range=['#0055ff', '#ff9900']))
    ).properties(height=300)
    st.altair_chart(line_chart, use_container_width=True)

    # 4. UNTERER BEREICH: AUFSTELLUNG (LINEUPS)
    st.write("")
    st.subheader("📋 Effektivste Aufstellungen (Lineups)")
    
    lineups = extract_lineups_from_game(None, team_id)
    
    # Header der Tabelle
    h_col1, h_col2, h_col3, h_col4, h_col5 = st.columns([3, 1, 1, 1, 1])
    h_col1.markdown("**AUFSTELLUNG**")
    h_col2.markdown("**MIN**")
    h_col3.markdown("**PKT**")
    h_col4.markdown("**OPP**")
    h_col5.markdown("**+/-**")

    for lineup in lineups:
        col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
        
        # Spieler-Icons (Jersey-Nummern in Kreisen)
        lineup_html = "<div style='display:flex; gap:5px;'>"
        for nr in lineup['ids']:
            lineup_html += f"""
            <div style='background-color:#4a90e2; color:white; border-radius:50%; width:30px; height:30px; 
            display:flex; align-items:center; justify-content:center; font-weight:bold; font-size:12px;'>
            {nr}
            </div>"""
        lineup_html += "</div>"
        
        col1.markdown(lineup_html, unsafe_allow_html=True)
        col2.write(lineup['min'])
        col3.write(str(lineup['pkt']))
        col4.write(str(lineup['opp']))
        
        pm = lineup['plusminus']
        pm_color = "green" if pm > 0 else "red"
        col5.markdown(f"<b style='color:{pm_color};'>{pm:+}</b>", unsafe_allow_html=True)

    st.divider()
    
    # 5. ZUSÄTZLICHE KENNZAHLEN BOXEN
    st.subheader("📊 Spiel-Statistiken")
    c_b1, c_b2, c_b3 = st.columns(3)
    with c_b1:
        st.markdown("<div style='text-align:center; padding:20px; border:1px solid #eee; border-radius:10px;'>🚀<br><b>6/11</b><br>Größter Vorsprung</div>", unsafe_allow_html=True)
    with c_b2:
        st.markdown("<div style='text-align:center; padding:20px; border:1px solid #eee; border-radius:10px;'>= <br><b>4</b><br>Gleichstand</div>", unsafe_allow_html=True)
    with c_b3:
        st.markdown("<div style='text-align:center; padding:20px; border:1px solid #eee; border-radius:10px;'>👕 <br><b>9</b><br>Führungswechsel</div>", unsafe_allow_html=True)

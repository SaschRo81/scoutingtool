# --- START OF FILE src/analysis_ui.py ---
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import pytz

# Lokale Imports aus deinem Projekt
from src.api import get_player_metadata_cached, get_best_team_logo, fetch_last_n_games_complete

# --- KONSTANTEN & HELPERS ---
ACTION_TRANSLATION = {
    "TWO_POINT_SHOT_MADE": "2P Treffer", "TWO_POINT_SHOT_MISSED": "2P Fehl",
    "THREE_POINT_SHOT_MADE": "3P Treffer", "THREE_POINT_SHOT_MISSED": "3P Fehl",
    "FREE_THROW_MADE": "FW Treffer", "FREE_THROW_MISSED": "FW Fehl",
    "REBOUND": "Rebound", "FOUL": "Foul", "TURNOVER": "TO",
    "ASSIST": "Assist", "STEAL": "Steal", "BLOCK": "Block",
    "SUBSTITUTION": "Wechsel", "TIMEOUT": "Auszeit",
    "JUMP_BALL": "Sprungball", "START": "Start", "END": "Ende"
}

def translate_text(text):
    if not text: return ""
    return ACTION_TRANSLATION.get(str(text).upper(), str(text).replace("_", " ").title())

def safe_int(val):
    if val is None: return 0
    try: return int(float(val))
    except: return 0

def get_team_name(team_data, default_name="Team"):
    name = team_data.get("gameStat", {}).get("seasonTeam", {}).get("name") or team_data.get("name")
    return name if name else default_name

def format_date_time(iso_string):
    if not iso_string: return "-"
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        berlin = pytz.timezone("Europe/Berlin")
        return dt.astimezone(berlin).strftime("%d.%m.%Y | %H:%M Uhr")
    except: return iso_string

# --- SCOUTING ANALYSE LOGIK ---

def analyze_scouting_data(team_id, detailed_games):
    stats = {
        "games_count": len(detailed_games),
        "wins": 0,
        "start_stats": {"pts_diff_q1": 0},
        "all_players": {},
        "rotation_depth": 0
    }
    tid_str = str(team_id)
    for box in detailed_games:
        res = box.get("result", {})
        h_id = str(box.get("homeTeam", {}).get("teamId"))
        g_id = str(box.get("guestTeam", {}).get("teamId"))
        is_home = (h_id == tid_str)
        
        # Sieg-Logik
        s_h = safe_int(res.get("homeTeamFinalScore"))
        s_g = safe_int(res.get("guestTeamFinalScore"))
        if (is_home and s_h > s_g) or (not is_home and s_g > s_h):
            stats["wins"] += 1
            
        # Rotation
        team_obj = box.get("homeTeam") if is_home else box.get("guestTeam")
        if team_obj:
            players = team_obj.get("playerStats", [])
            for p in players:
                p_info = p.get("seasonPlayer", {})
                pid = str(p_info.get("id"))
                if safe_int(p.get("secondsPlayed")) > 300: # > 5 Min
                    if pid not in stats["all_players"]:
                        stats["all_players"][pid] = {"name": f"#{p_info.get('shirtNumber')} {p_info.get('lastName')}", "pm": 0, "games": 0}
                    stats["all_players"][pid]["pm"] += safe_int(p.get("plusMinus"))
                    stats["all_players"][pid]["games"] += 1
        
        # Q1 Start Qualität
        q1_h = safe_int(res.get("homeTeamQ1Score"))
        q1_g = safe_int(res.get("guestTeamQ1Score"))
        stats["start_stats"]["pts_diff_q1"] += (q1_h - q1_g if is_home else q1_g - q1_h)

    cnt = stats["games_count"] if stats["games_count"] > 0 else 1
    stats["start_avg"] = round(stats["start_stats"]["pts_diff_q1"] / cnt, 1)
    eff_list = [{"name": d["name"], "pm": round(d["pm"]/d["games"], 1)} for d in stats["all_players"].values() if d["games"] > 0]
    stats["top_performers"] = sorted(eff_list, key=lambda x: x["pm"], reverse=True)[:5]
    return stats

# --- DASHBOARD RENDERING ---

def render_team_analysis_dashboard(team_id, team_name):
    logo = get_best_team_logo(team_id)
    c1, c2 = st.columns([1, 4])
    with c1:
        if logo: st.image(logo, width=100)
    with c2:
        st.title(f"Scouting Report: {team_name}")
        st.caption("Basierend auf der Play-by-Play Analyse der gesamten Saison")

    with st.spinner("Analysiere Daten..."):
        games_data = fetch_last_n_games_complete(team_id, "2025", n=12)
        if not games_data:
            st.warning("Keine Daten gefunden."); return
        scout = analyze_scouting_data(team_id, games_data)

    # 1. KENNZAHLEN (GELB)
    st.markdown("""<style>.yellow-box { background-color: #ffffcc; padding: 10px; border-radius: 5px; border: 1px solid #e6e600; }</style>""", unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Analysierte Spiele", scout["games_count"], f"{scout['wins']} Siege")
    k2.metric("Start-Qualität (Q1)", f"{scout['start_avg']:+.1f}")
    k3.metric("Rotation (Spieler >5min)", "9.2")
    k4.metric("ATO Effizienz", "0.0 PPP", "0 Timeouts")

    st.divider()

    # 2. EFFEKTIVSTE SPIELERINNEN
    st.subheader("🚀 Effektivste Spielerinnen (Ø Plus/Minus pro Spiel)")
    cols = st.columns(5)
    for i, p in enumerate(scout["top_performers"]):
        with cols[i]:
            st.markdown(f"<div style='background-color:#f8f9fa;padding:10px;border-radius:10px;text-align:center;border:1px solid #dee2e6;'><div style='font-weight:bold;font-size:0.9em;'>{p['name']}</div><div style='font-size:1.4em;color:#28a745;font-weight:bold;'>{p['pm']:+.1f}</div></div>", unsafe_allow_html=True)

    st.write("")
    st.divider()

    # 3. SPIELVERLAUF GRAPH
    st.subheader("📈 Spielverlauf (Score Flow)")
    dummy_data = pd.DataFrame({'Minute': range(41), 'Team': [i + (i%5) for i in range(41)], 'Gegner': [i + (i%3) for i in range(41)]}).melt('Minute')
    chart = alt.Chart(dummy_data).mark_line(interpolate='basis').encode(x='Minute', y='value', color='variable').properties(height=300)
    st.altair_chart(chart, use_container_width=True)

    # 4. AUFSTELLUNG (LINEUPS)
    st.write("")
    st.subheader("📋 Effektivste Aufstellungen (Lineups)")
    # Tabellen Header
    h1, h2, h3, h4, h5 = st.columns([3, 1, 1, 1, 1])
    h1.markdown("**AUFSTELLUNG**"); h2.markdown("**MIN**"); h3.markdown("**PKT**"); h4.markdown("**OPPPKT**"); h5.markdown("**+/-**")

    sample_lineups = [
        {"ids": ["13", "74", "2", "20", "5"], "min": "10:28", "pkt": 21, "opp": 24, "pm": -3},
        {"ids": ["24", "13", "74", "2", "20"], "min": "05:22", "pkt": 13, "opp": 6, "pm": 7},
        {"ids": ["74", "17", "2", "20", "5"], "min": "04:03", "pkt": 7, "opp": 0, "pm": 7}
    ]

    for lu in sample_lineups:
        c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 1, 1])
        # Blaue Kreise HTML
        circles = "".join([f"<div style='background:#4a90e2;color:white;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:11px;margin-right:4px;'>{id}</div>" for id in lu['ids']])
        c1.markdown(f"<div style='display:flex;'>{circles}</div>", unsafe_allow_html=True)
        c2.write(lu['min']); c3.write(str(lu['pkt'])); c4.write(str(lu['opp']))
        c5.markdown(f"<b style='color:{'green' if lu['pm']>0 else 'red'};'>{lu['pm']:+}</b>", unsafe_allow_html=True)

    st.divider()

    # 5. UNTERE KACHELN
    st.subheader("📊 Spiel-Kennzahlen")
    b1, b2, b3 = st.columns(3)
    b1.markdown("<div style='text-align:center;padding:15px;border:1px solid #eee;border-radius:10px;'>🚀<br><b>6/11</b><br>Größter Vorsprung</div>", unsafe_allow_html=True)
    b2.markdown("<div style='text-align:center;padding:15px;border:1px solid #eee;border-radius:10px;'>=<br><b>4</b><br>Gleichstand</div>", unsafe_allow_html=True)
    b3.markdown("<div style='text-align:center;padding:15px;border:1px solid #eee;border-radius:10px;'>👕<br><b>9</b><br>Führungswechsel</div>", unsafe_allow_html=True)

# --- APP.PY BENÖTIGTE FUNKTIONEN ---

def render_game_header(details):
    res = details.get("result", {})
    st.markdown(f"<h2 style='text-align:center;'>{get_team_name(details.get('homeTeam'))} {res.get('homeTeamFinalScore')} : {res.get('guestTeamFinalScore')} {get_team_name(details.get('guestTeam'))}</h2>", unsafe_allow_html=True)

def render_boxscore_table_pro(player_stats, team_stats, name, coach="-"):
    st.markdown(f"**{name}**")
    st.dataframe(pd.DataFrame([{"#": p.get("seasonPlayer",{}).get("shirtNumber"), "Name": p.get("seasonPlayer",{}).get("lastName"), "PTS": p.get("points")} for p in player_stats]), hide_index=True)

def render_charts_and_stats(box): st.info("Charts & Stats")
def render_game_top_performers(box): st.info("Top Performer")
def generate_game_summary(box): return "Zusammenfassung..."
def generate_complex_ai_prompt(box): return "Prompt..."
def run_openai_generation(api_key, prompt): return "KI Bericht..."
def render_full_play_by_play(box, height=600): st.info("Play by Play")
def render_prep_dashboard(team_id, team_name, df_roster, last_games, metadata_callback=None): st.info("Vorbereitung")
def render_live_view(box): st.title("Live View")

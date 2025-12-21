import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import pytz
from src.api import fetch_team_rank, get_player_metadata_cached

# --- HELPERS ---

ACTION_TRANSLATION = {
    "TWO_POINT_SHOT_MADE": "2P Treffer", "TWO_POINT_SHOT_MISSED": "2P Fehl",
    "THREE_POINT_SHOT_MADE": "3P Treffer", "THREE_POINT_SHOT_MISSED": "3P Fehl",
    "FREE_THROW_MADE": "FW Treffer", "FREE_THROW_MISSED": "FW Fehl",
    "REBOUND": "Rebound", "FOUL": "Foul", "TURNOVER": "TO",
    "ASSIST": "Assist", "STEAL": "Steal", "BLOCK": "Block"
}

def translate_text(text):
    if not text: return ""
    text_upper = str(text).upper()
    if text_upper in ACTION_TRANSLATION: return ACTION_TRANSLATION[text_upper]
    return text.replace("_", " ").capitalize()

def safe_int(val):
    if val is None: return 0
    try: return int(float(val))
    except: return 0

def get_team_name(team_data, default_name="Team"):
    name = team_data.get("gameStat", {}).get("seasonTeam", {}).get("name")
    return name if name else team_data.get("name", default_name)

def convert_elapsed_to_remaining(time_str, period):
    if not time_str: return "-"
    base = 10 if safe_int(period) <= 4 else 5
    try:
        parts = time_str.split(":")
        sec = int(parts[0])*60 + int(parts[1]) if len(parts)==2 else (int(parts[0])*3600 + int(parts[1])*60 + int(parts[2]))
        rem = (base * 60) - sec
        return f"{max(0, rem)//60:02d}:{max(0, rem)%60:02d}"
    except: return time_str

# --- RENDERING ---

def render_full_play_by_play(box, height=600, reverse=False):
    actions = box.get("actions", [])
    if not actions: return st.info("Keine Play-by-Play Daten.")
    data = []
    for act in actions:
        time_label = f"Q{act.get('period','?')} {convert_elapsed_to_remaining(act.get('gameTime'), act.get('period'))}"
        score = f"{safe_int(act.get('homeTeamPoints'))}:{safe_int(act.get('guestTeamPoints'))}"
        data.append({"Zeit": time_label, "Score": score, "Aktion": translate_text(act.get("type"))})
    df = pd.DataFrame(data)
    if reverse: df = df.iloc[::-1]
    st.dataframe(df, use_container_width=True, hide_index=True, height=height)

def render_game_header(details):
    res = details.get("result", {})
    st.markdown(f"<h1 style='text-align: center;'>{get_team_name(details.get('homeTeam'))} {res.get('homeTeamFinalScore',0)} : {res.get('guestTeamFinalScore',0)} {get_team_name(details.get('guestTeam'))}</h1>", unsafe_allow_html=True)

def render_boxscore_table_pro(player_stats, team_stats, title):
    data = []
    for p in player_stats:
        data.append({"#": p.get("seasonPlayer",{}).get("shirtNumber"), "Name": p.get("seasonPlayer",{}).get("lastName"), "PTS": safe_int(p.get("points")), "REB": safe_int(p.get("totalRebounds")), "AST": safe_int(p.get("assists"))})
    st.subheader(title)
    st.dataframe(pd.DataFrame(data), hide_index=True, use_container_width=True)

def render_charts_and_stats(box):
    st.info("Team-Statistiken werden hier visualisiert.")

def generate_game_summary(box):
    return "Kurzbericht: Ein spannendes Spiel mit vielen Highlights."

def render_game_top_performers(box):
    st.write("Top Performer Anzeige...")

def generate_complex_ai_prompt(box):
    return "ChatGPT Prompt für Spielbericht..."

def render_prep_dashboard(team_id, team_name, df_roster, last_games, metadata_callback=None):
    from src.config import SEASON_ID
    rank_info = fetch_team_rank(team_id, SEASON_ID)
    st.subheader(f"Analyse: {team_name}")
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown("#### Top 5 Spieler (PPG)")
        top5 = df_roster.sort_values(by="PPG", ascending=False).head(5)
        for _, r in top5.iterrows():
            with st.container(border=True):
                col_img, col_stats = st.columns([1, 3])
                meta = metadata_callback(r["PLAYER_ID"]) if metadata_callback else {}
                with col_img: st.markdown("👤")
                with col_stats:
                    st.markdown(f"**#{r['NR']} {r['NAME_FULL']}**")
                    st.write(f"PPG: {r['PPG']} | REB: {r['TOT']} | AST: {r['AS']}")
    with c2:
        if rank_info:
            st.markdown(f"<div style='background:#f0f0f0; padding:20px; border-radius:10px; text-align:center;'><h4>Tabellenplatz</h4><h1 style='color:#28a745;'>{rank_info['rank']}.</h1><p>Bilanz: {rank_info['totalVictories']}-{rank_info['totalLosses']}</p></div>", unsafe_allow_html=True)
        st.markdown("#### Formkurve")
        for g in last_games[:5]: st.write(f"{g['date']}: {g['score']}")

def render_live_view(box):
    res = box.get("result", {})
    s_h, s_g = res.get('homeTeamFinalScore', 0), res.get('guestTeamFinalScore', 0)
    if s_h == 0 and s_g == 0 and box.get("actions"):
        last = box["actions"][-1]
        s_h, s_g = safe_int(last.get("homeTeamPoints")), safe_int(last.get("guestTeamPoints"))
    st.markdown(f"<div style='text-align:center;background:#222;color:#fff;padding:10px;border-radius:10px;margin-bottom:15px;'><h1>{s_h} : {s_g}</h1></div>", unsafe_allow_html=True)
    c_stats, c_ticker = st.columns([2.5, 1])
    with c_stats:
        col_h, col_g = st.columns(2)
        with col_h: 
            st.markdown(f"**{get_team_name(box.get('homeTeam'))}**")
            render_boxscore_table_pro(box.get("homeTeam",{}).get("playerStats",[]), {}, "Heim")
        with col_g: 
            st.markdown(f"**{get_team_name(box.get('guestTeam'))}**")
            render_boxscore_table_pro(box.get("guestTeam",{}).get("playerStats",[]), {}, "Gast")
    with c_ticker:
        st.subheader("Live Ticker")
        render_full_play_by_play(box, height=500, reverse=True)

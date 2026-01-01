# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import pytz

# Absicherung: Falls OpenAI nicht installiert ist, stürzt die App nicht ab
try:
    import openai
except ImportError:
    openai = None

# Lokale Imports
from src.api import get_player_metadata_cached, get_best_team_logo, fetch_last_n_games_complete

# --- 1. HELPERS ---
def safe_int(val):
    if val is None: return 0
    try: return int(float(val))
    except: return 0

def get_team_name(team_data, default_name="Team"):
    if not team_data: return default_name
    name = team_data.get("gameStat", {}).get("seasonTeam", {}).get("name") or team_data.get("name")
    return name if name else default_name

def format_min(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"

# --- 2. INTELLIGENTER LINEUP-TRACKER ---
def calculate_real_lineups(team_id, detailed_games):
    lineup_stats = {}
    tid_str = str(team_id)
    for box in detailed_games:
        actions = sorted(box.get("actions", []), key=lambda x: x.get('actionNumber', 0))
        h_id = str(box.get("homeTeam", {}).get("teamId"))
        is_home = (h_id == tid_str)
        my_team = box.get("homeTeam") if is_home else box.get("guestTeam")
        
        current_lineup = set([str(p.get("seasonPlayer",{}).get("id")) for p in my_team.get("playerStats", []) if p.get("isStartingFive")])
        last_secs, last_h, last_g = 0, 0, 0
        
        for act in actions:
            raw_time = act.get("gameTime", "00:00")
            try:
                parts = raw_time.split(':')
                curr_secs = (act.get("period", 1)-1)*600 + (int(parts[-2])*60 + int(parts[-1]))
            except: curr_secs = last_secs
            
            # Auto-Korrektur falls Spieler Aktion macht
            act_pid = str(act.get("seasonPlayerId"))
            if str(act.get("seasonTeamId")) == tid_str and act_pid and act_pid != "None":
                if act_pid not in current_lineup:
                    if len(current_lineup) >= 5: current_lineup.pop()
                    current_lineup.add(act_pid)

            if len(current_lineup) == 5:
                l_key = tuple(sorted(list(current_lineup)))
                if l_key not in lineup_stats: lineup_stats[l_key] = {"secs": 0, "pts_for": 0, "pts_agn": 0}
                lineup_stats[l_key]["secs"] += max(0, curr_secs - last_secs)
                new_h, new_g = safe_int(act.get("homeTeamPoints")), safe_int(act.get("guestTeamPoints"))
                if is_home:
                    lineup_stats[l_key]["pts_for"] += max(0, new_h - last_h)
                    lineup_stats[l_key]["pts_agn"] += max(0, new_g - last_g)
                else:
                    lineup_stats[l_key]["pts_for"] += max(0, new_g - last_g)
                    lineup_stats[l_key]["pts_agn"] += max(0, new_h - last_h)
            last_secs, last_h, last_g = curr_secs, safe_int(act.get("homeTeamPoints")), safe_int(act.get("guestTeamPoints"))
    
    res = []
    for ids, d in lineup_stats.items():
        if d["secs"] > 45:
            res.append({"ids": list(ids), "min": format_min(d["secs"]), "pkt": d["pts_for"], "opp": d["pts_agn"], "pm": d["pts_for"] - d["pts_agn"]})
    return sorted(res, key=lambda x: x["pm"], reverse=True)[:3]

# --- 3. SCOUTING LOGIK ---
def analyze_scouting_data(team_id, detailed_games):
    stats = {"games_count": len(detailed_games), "wins": 0, "p_diff": 0, "all_players": {}, "jersey_map": {}}
    tid_str = str(team_id)
    for box in detailed_games:
        res = box.get("result", {})
        is_home = (str(box.get("homeTeam", {}).get("teamId")) == tid_str)
        s_h, s_g = safe_int(res.get("homeTeamFinalScore")), safe_int(res.get("guestTeamFinalScore"))
        if (is_home and s_h > s_g) or (not is_home and s_g > s_h): stats["wins"] += 1
        my_team = box.get("homeTeam") if is_home else box.get("guestTeam")
        for p in my_team.get("playerStats", []):
            p_i = p.get("seasonPlayer", {})
            nr, name, pid = str(p_i.get("shirtNumber", "?")), p_i.get("lastName", "Unk"), str(p_i.get("id"))
            stats["jersey_map"][pid] = {"nr": nr, "name": name}
            if safe_int(p.get("secondsPlayed")) > 300:
                if pid not in stats["all_players"]: stats["all_players"][pid] = {"name": f"#{nr} {name}", "pm": 0, "games": 0}
                stats["all_players"][pid]["pm"] += safe_int(p.get("plusMinus")); stats["all_players"][pid]["games"] += 1
        stats["p_diff"] += (safe_int(res.get("homeTeamQ1Score")) - safe_int(res.get("guestTeamQ1Score")) if is_home else safe_int(res.get("guestTeamQ1Score")) - safe_int(res.get("homeTeamQ1Score")))
    stats["start_avg"] = round(stats["p_diff"] / max(1, stats["games_count"]), 1)
    eff = [{"name": d["name"], "pm": round(d["pm"]/d["games"], 1)} for d in stats["all_players"].values() if d["games"] > 0]
    stats["top_performers"] = sorted(eff, key=lambda x: x["pm"], reverse=True)[:5]
    return stats

# --- 4. DASHBOARD UI ---
def render_team_analysis_dashboard(team_id, team_name):
    logo = get_best_team_logo(team_id)
    c1, c2 = st.columns([1, 4])
    with c1: 
        if logo: st.image(logo, width=100)
    with c2:
        st.title(f"Scouting Report: {team_name}")
    
    with st.spinner("Lade Daten..."):
        games = fetch_last_n_games_complete(team_id, "2025", n=12)
        if not games: 
            st.warning("Keine Daten gefunden."); return
        scout = analyze_scouting_data(team_id, games)
        real_lineups = calculate_real_lineups(team_id, games)

    # Metrics
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Spiele", scout["games_count"], f"{scout['wins']} Siege")
    k2.metric("Start-Q (Q1)", f"{scout['start_avg']:+.1f}")
    k3.metric("Rotation", "9.2")
    k4.metric("ATO", "0.0 PPP")

    st.divider()
    st.subheader("📋 Lineups")
    st.markdown("""<style>.c-box { display:flex; flex-direction:column; align-items:center; width:50px; } .circle { background:#4a90e2; color:white; border-radius:50%; width:32px; height:32px; display:flex; align-items:center; justify-content:center; font-weight:bold; font-size:13px; } .n-label { font-size:10px; color:#666; margin-top:4px; text-align:center; }</style>""", unsafe_allow_html=True)

    for lu in real_lineups:
        cols = st.columns([4, 1, 1, 1, 1])
        lineup_html = "<div style='display:flex; gap:10px;'>"
        for pid in lu['ids']:
            p_info = scout["jersey_map"].get(pid, {"nr": "?", "name": "Unk"})
            lineup_html += f"<div class='c-box'><div class='circle'>{p_info['nr']}</div><div class='n-label'>{p_info['name']}</div></div>"
        lineup_html += "</div>"
        with cols[0]: st.markdown(lineup_html, unsafe_allow_html=True)
        with cols[1]: st.write(f"\n{lu['min']}")
        with cols[2]: st.write(f"\n{lu['pkt']}")
        with cols[3]: st.write(f"\n{lu['opp']}")
        with cols[4]: st.markdown(f"\n<b style='color:{'green' if lu['pm']>0 else 'red'};'>{lu['pm']:+}</b>", unsafe_allow_html=True)

    # Prompt
    st.divider()
    st.subheader("🤖 KI Prompt")
    st.code(f"Analysiere Team {team_name}...", language="text")

# --- 5. COMPATIBILITY SKELETONS (WICHTIG!) ---
def render_game_header(details): pass
def render_boxscore_table_pro(p, t, n, c="-"): pass
def render_charts_and_stats(box): pass
def render_game_top_performers(box): pass
def generate_game_summary(box): return ""
def generate_complex_ai_prompt(box): return ""
def run_openai_generation(api_key, prompt): return ""
def render_full_play_by_play(box, height=600): pass
def render_prep_dashboard(t, n, d, s, m=None): pass
def render_live_view(box): pass

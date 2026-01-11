# --- START OF FILE src/analysis_ui.py ---
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import pytz
import openai
from src.api import get_player_metadata_cached, get_best_team_logo, fetch_last_n_games_complete

# --- KONSTANTEN & HELPERS ---
ACTION_TRANSLATION = {
    "TWO_POINT_SHOT_MADE": "2P Treffer", "TWO_POINT_SHOT_MISSED": "2P Fehl",
    "THREE_POINT_SHOT_MADE": "3P Treffer", "THREE_POINT_SHOT_MISSED": "3P Fehl",
    "FREE_THROW_MADE": "FW Treffer", "FREE_THROW_MISSED": "FW Fehl",
    "REBOUND": "Rebound", "FOUL": "Foul", "TURNOVER": "TO",
    "ASSIST": "Assist", "STEAL": "Steal", "BLOCK": "Block",
    "SUBSTITUTION": "Wechsel", "TIMEOUT": "Auszeit",
    "JUMP_BALL": "Sprungball", "START": "Start", "END": "Ende",
    "TWO_POINT_THROW": "2P Wurf", "THREE_POINT_THROW": "3P Wurf",
    "FREE_THROW": "Freiwurf", "layup": "Korbleger", "jump_shot": "Sprung",
    "dunk": "Dunk", "offensive": "Off", "defensive": "Def",
    "personal_foul": "Persönlich", "technical_foul": "Technisch",
    "unsportsmanlike_foul": "Unsportlich"
}

def translate_text(text):
    if not text: return ""
    text_upper = str(text).upper()
    if text_upper in ACTION_TRANSLATION: return ACTION_TRANSLATION[text_upper]
    clean_text = text.replace("_", " ").lower()
    for eng, ger in ACTION_TRANSLATION.items():
        if eng.lower() in clean_text: clean_text = clean_text.replace(eng.lower(), ger)
    return clean_text.capitalize()

def safe_int(val):
    if val is None: return 0
    try: return int(float(val))
    except: return 0

def get_team_name(team_data, default_name="Team"):
    if not team_data: return default_name
    name = team_data.get("gameStat", {}).get("seasonTeam", {}).get("name")
    if name: return name
    name = team_data.get("seasonTeam", {}).get("name")
    if name: return name
    return team_data.get("name", default_name)

def format_date_time(iso_string):
    if not iso_string: return "-"
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        berlin = pytz.timezone("Europe/Berlin")
        return dt.astimezone(berlin).strftime("%d.%m.%Y | %H:%M Uhr")
    except: return iso_string

def get_player_lookup(box):
    lookup = {}
    for team_key in ['homeTeam', 'guestTeam']:
        for p in box.get(team_key, {}).get('playerStats', []):
            pid = str(p.get('seasonPlayer', {}).get('id'))
            name = f"{p.get('seasonPlayer', {}).get('lastName', '')}" 
            nr = p.get('seasonPlayer', {}).get('shirtNumber', '')
            lookup[pid] = f"#{nr} {name}"
    return lookup

def get_player_team_map(box):
    player_team = {}
    h_name = get_team_name(box.get("homeTeam", {}), "Heim")
    g_name = get_team_name(box.get("guestTeam", {}), "Gast")
    for p in box.get("homeTeam", {}).get('playerStats', []):
        player_team[str(p.get('seasonPlayer', {}).get('id'))] = h_name
    for p in box.get("guestTeam", {}).get('playerStats', []):
        player_team[str(p.get('seasonPlayer', {}).get('id'))] = g_name
    return player_team

def get_time_info(time_str, period):
    """Berechnet (Restzeit, Originalzeit)."""
    if not time_str: return "10:00", "00:00"
    p_int = safe_int(period)
    base_min = 5 if p_int > 4 else 10
    total_sec = base_min * 60
    elapsed_sec = 0
    try:
        if "PT" in str(time_str):
            t = str(time_str).replace("PT", "").replace("S", "")
            if "M" in t:
                parts = t.split("M")
                elapsed_sec = int(float(parts[0])) * 60 + int(float(parts[1] or 0))
            else: elapsed_sec = int(float(t))
        elif ":" in str(time_str):
            parts = str(time_str).split(":")
            if len(parts) == 3: elapsed_sec = int(parts[0])*3600 + int(parts[1])*60 + int(parts[2])
            elif len(parts) == 2: elapsed_sec = int(parts[0])*60 + int(parts[1])
        else: elapsed_sec = int(float(time_str))
        rem_sec = total_sec - elapsed_sec
        if rem_sec < 0: rem_sec = 0
        return f"{rem_sec // 60:02d}:{rem_sec % 60:02d}", f"{elapsed_sec // 60:02d}:{elapsed_sec % 60:02d}"
    except: return "10:00", str(time_str)

def analyze_game_flow(actions, home_name, guest_name):
    if not actions: return "Keine Play-by-Play Daten verfügbar."
    lead_changes, ties = 0, 0
    last_leader = None
    sorted_actions = sorted(actions, key=lambda x: x.get('actionNumber', 0))
    run_h, run_g = 0, 0
    enriched = []
    for act in sorted_actions:
        if act.get("homeTeamPoints") is not None:
            run_h, run_g = safe_int(act.get("homeTeamPoints")), safe_int(act.get("guestTeamPoints"))
        current_leader = 'home' if run_h > run_g else ('guest' if run_g > run_h else 'tie')
        if last_leader is not None and current_leader != last_leader:
            if current_leader == 'tie': ties += 1
            else: lead_changes += 1
        last_leader = current_leader
        act['_score'] = f"{run_h}:{run_g}"
        enriched.append(act)
    rel_types = ["TWO_POINT_SHOT_MADE", "THREE_POINT_SHOT_MADE", "FREE_THROW_MADE", "TURNOVER", "FOUL", "TIMEOUT"]
    filtered = [a for a in enriched if a.get("type") in rel_types]
    last_events = filtered[-20:] 
    crunch = "\n**⏱️ Die Schlussphase (PBP):**"
    for ev in last_events:
        desc = translate_text(ev.get("type", ""))
        if ev.get("points"): desc += f" (+{ev.get('points')})"
        crunch += f"\n- {ev.get('_score')}: {desc}"
    return f"Führungswechsel: {lead_changes}, Unentschieden: {ties}.{crunch}"

# --- EXPORTS FÜR APP.PY ---

def generate_complex_ai_prompt(box):
    if not box: return "Keine Daten."
    h_data, g_data = box.get("homeTeam", {}), box.get("guestTeam", {})
    h_name, g_name = get_team_name(h_data), get_team_name(g_data)
    res = box.get("result", {})
    pbp_summary = analyze_game_flow(box.get("actions", []), h_name, g_name)
    is_home_jena = "Jena" in h_name or "VIMODROM" in h_name
    opponent = g_name if is_home_jena else h_name
    location = "Heimspiel" if is_home_jena else "Auswärtsspiel"
    def get_stats_str(td):
        s = td.get("gameStat", {})
        top_p = sorted([p for p in td.get("playerStats", [])], key=lambda x: safe_int(x.get("points")), reverse=True)[:3]
        top_str = ", ".join([f"{p.get('seasonPlayer', {}).get('lastName')} ({p.get('points')})" for p in top_p])
        return f"Wurfquote: {safe_int(s.get('fieldGoalsSuccessPercent'))}%, Reb: {safe_int(s.get('totalRebounds'))}. Top: {top_str}"

    return f"""Du agierst als erfahrener Sportjournalist für VIMODROM Baskets Jena. Erstelle 3 SEO-Artikel (Website, Liga, Magazin) & Storytelling-Bericht gegen {opponent}.
Ergebnis: {h_name} {res.get('homeTeamFinalScore')} : {res.get('guestTeamFinalScore')} {g_name}.
Viertel: Q1 {res.get('homeTeamQ1Score')}:{res.get('guestTeamQ1Score')}, Q2 {res.get('homeTeamQ2Score')}:{res.get('guestTeamQ2Score')}, Q3 {res.get('homeTeamQ3Score')}:{res.get('guestTeamQ3Score')}, Q4 {res.get('homeTeamQ4Score')}:{res.get('guestTeamQ4Score')}.
Ort: {location} in {box.get('venue', {}).get('name', 'Halle')}.
Stats {h_name}: {get_stats_str(h_data)}.
Stats {g_name}: {get_stats_str(g_data)}.
PBP-Analyse: {pbp_summary}"""

def render_game_header(details):
    h_name, g_name = get_team_name(details.get("homeTeam")), get_team_name(details.get("guestTeam"))
    res = details.get("result", {})
    st.markdown(f"<h2 style='text-align:center;'>{h_name} {res.get('homeTeamFinalScore', 0)} : {res.get('guestTeamFinalScore', 0)} {g_name}</h2>", unsafe_allow_html=True)

def render_boxscore_table_pro(player_stats, team_stats_official, team_name, coach_name="-"):
    if not player_stats: return
    data = [{"#": p.get("seasonPlayer",{}).get("shirtNumber"), "Name": p.get("seasonPlayer",{}).get("lastName"), "Min": f"{safe_int(p.get('secondsPlayed'))//60:02d}:00", "PTS": safe_int(p.get("points"))} for p in player_stats]
    st.markdown(f"#### {team_name} (HC: {coach_name})")
    st.dataframe(pd.DataFrame(data), hide_index=True, use_container_width=True)

def render_game_top_performers(box):
    st.markdown("### Top Performer")
    c1, c2 = st.columns(2)
    for i, team in enumerate(["homeTeam", "guestTeam"]):
        td = box.get(team, {})
        players = sorted([p for p in td.get("playerStats", [])], key=lambda x: safe_int(x.get("points")), reverse=True)[:3]
        with [c1, c2][i]:
            st.write(f"**{get_team_name(td)}**")
            for p in players: st.write(f"{p.get('seasonPlayer',{}).get('lastName')}: {p.get('points')} Pkt")

def render_charts_and_stats(box):
    render_live_comparison_bars(box)

def generate_game_summary(box):
    return "Zusammenfassung für " + get_team_name(box.get("homeTeam"))

def run_openai_generation(api_key, prompt):
    return "KI-Dienst bereit."

# --- LIVE VIEW & TICKER ---

def render_live_comparison_bars(box):
    h_stat, g_stat = box.get("homeTeam",{}).get("gameStat",{}), box.get("guestTeam",{}).get("gameStat",{})
    h_name, g_name = get_team_name(box.get("homeTeam")), get_team_name(box.get("guestTeam"))
    st.markdown("""<style>.stat-container { margin-bottom: 10px; width: 100%; }.stat-label { text-align: center; font-weight: bold; font-size: 0.8em; }.bar-wrapper { display: flex; align-items: center; justify-content: center; gap: 5px; height: 10px; }.bar-bg { background-color: #eee; flex-grow: 1; height: 100%; position: relative; }.bar-fill-home { background-color: #e35b00; height: 100%; position: absolute; right: 0; }.bar-fill-guest { background-color: #333; height: 100%; position: absolute; left: 0; }.val-text { width: 60px; font-weight: bold; font-size: 0.8em; }</style>""", unsafe_allow_html=True)
    metrics = [("2 PUNKTE", "twoPointShotsMade"), ("3 PUNKTE", "threePointShotsMade"), ("FIELDGOALS", "fieldGoalsMade"), ("REBOUNDS", "totalRebounds"), ("ASSISTS", "assists"), ("STEALS", "steals")]
    for label, key in metrics:
        hv, gv = safe_int(h_stat.get(key)), safe_int(g_stat.get(key))
        max_v = max(hv, gv, 1)
        st.markdown(f'<div class="stat-container"><div class="stat-label">{label}</div><div class="bar-wrapper"><div class="val-text" style="text-align:right;">{hv}</div><div class="bar-bg"><div class="bar-fill-home" style="width:{(hv/max_v)*100}%;"></div></div><div class="bar-bg"><div class="bar-fill-guest" style="width:{(gv/max_v)*100}%;"></div></div><div class="val-text" style="text-align:left;">{gv}</div></div></div>', unsafe_allow_html=True)

def render_full_play_by_play(box, height=600):
    actions = box.get("actions", [])
    if not actions: return
    player_map = get_player_lookup(box); team_map = get_player_team_map(box)
    h_id, g_id = str(box.get("homeTeam",{}).get("seasonTeamId")), str(box.get("guestTeam",{}).get("seasonTeamId"))
    h_name, g_name = get_team_name(box.get("homeTeam")), get_team_name(box.get("guestTeam"))
    data = []
    rh, rg = 0, 0
    for act in sorted(actions, key=lambda x: x.get('actionNumber', 0)):
        if act.get("homeTeamPoints") is not None: rh, rg = safe_int(act.get("homeTeamPoints")), safe_int(act.get("guestTeamPoints"))
        t_rem, t_orig = get_time_info(act.get("gameTime") or act.get("timeInGame"), act.get("period"))
        pid = str(act.get("seasonPlayerId"))
        team = team_map.get(pid) or (h_name if str(act.get("seasonTeamId")) == h_id else (g_name if str(act.get("seasonTeamId")) == g_id else "-"))
        data.append({"Zeit": f"Q{act.get('period')} | {t_rem} ({t_orig})", "Score": f"{rh}:{rg}", "Team": team, "Spieler": player_map.get(pid, ""), "Aktion": translate_text(act.get("type"))})
    df = pd.DataFrame(data)
    if not df.empty: df = df.iloc[::-1]
    st.dataframe(df, use_container_width=True, hide_index=True, height=height)

def render_live_view(box):
    if not box: return
    h_data, g_data = box.get("homeTeam", {}), box.get("guestTeam", {})
    h_name, g_name = get_team_name(h_data), get_team_name(g_data)
    res = box.get("result", {}); sh, sg = safe_int(res.get('homeTeamFinalScore')), safe_int(res.get('guestTeamFinalScore'))
    period = res.get('period') or box.get('period', 1)
    t_rem, t_orig = get_time_info(box.get('gameTime'), period)
    st.markdown(f"<div style='text-align:center;background:#222;color:#fff;padding:15px;border-radius:10px;'><h3>{h_name} {sh} : {sg} {g_name}</h3><h4 style='color:#ffcc00;'>Q{period} | {t_rem} <span style='font-size:0.6em;color:#fff;'>(gespielt {t_orig})</span></h4></div>", unsafe_allow_html=True)
    t1, t2, t3 = st.tabs(["📋 Boxscore", "📊 Team-Vergleich", "📜 Play-by-Play"])
    with t1:
        c1, c2 = st.columns(2)
        with c1: st.write(f"**{h_name}**"); st.dataframe(create_live_boxscore_df(h_data), hide_index=True, use_container_width=True)
        with c2: st.write(f"**{g_name}**"); st.dataframe(create_live_boxscore_df(g_data), hide_index=True, use_container_width=True)
    with t2: render_live_comparison_bars(box)
    with t3: render_full_play_by_play(box)

def create_live_boxscore_df(team_data):
    data = [{"#": p.get("seasonPlayer",{}).get("shirtNumber"), "Name": p.get("seasonPlayer",{}).get("lastName"), "PTS": safe_int(p.get("points")), "REB": safe_int(p.get("totalRebounds"))} for p in team_data.get("playerStats", [])]
    return pd.DataFrame(data).sort_values(by="PTS", ascending=False) if data else pd.DataFrame()

# --- SCOUTING ---

def render_prep_dashboard(team_id, team_name, df_roster, last_games, metadata_callback=None):
    st.subheader(f"Scouting: {team_name}")
    c1, c2 = st.columns([2, 1])
    with c1:
        top = df_roster.sort_values(by="PPG", ascending=False).head(4)
        for _, r in top.iterrows():
            with st.container(border=True):
                st.write(f"**#{r.get('NR')} {r.get('NAME_FULL')}** ({r.get('PPG')} PPG)")
    with c2:
        for g in last_games[:5]: st.write(f"{g.get('date').split(' ')[0]}: {g.get('score')}")

def analyze_scouting_data(team_id, detailed_games):
    return { "games_count": len(detailed_games), "wins": 0, "ato_stats": {"possessions": 0, "points": 0}, "start_stats": {"avg_diff": 0}, "rotation_depth": 8, "top_scorers_list": [] }

def prepare_ai_scouting_context(team_name, detailed_games, team_id):
    return f"KI Context für {team_name}"

def render_team_analysis_dashboard(team_id, team_name):
    logo = get_best_team_logo(team_id); c1, c2 = st.columns([1, 4])
    if logo: c1.image(logo, width=100)
    c2.title(f"Team Analyse: {team_name}")
    games = fetch_last_n_games_complete(team_id, "2025", n=50)
    scout = analyze_scouting_data(team_id, games)
    st.metric("Spiele", scout["games_count"])
    st.code(prepare_ai_scouting_context(team_name, games, team_id))

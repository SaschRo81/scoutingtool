import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import pytz
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

def safe_div(numerator, denominator):
    if denominator == 0: return 0.0
    return round((numerator / denominator) * 100, 1)

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

def get_team_ids(team_data):
    ids = []
    if team_data:
        ids.extend([str(team_data.get("seasonTeamId", "")), str(team_data.get("teamId", "")), str(team_data.get("seasonTeam", {}).get("id", ""))])
    return list(set(filter(None, ids)))

def get_time_info(time_str, period):
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
        return f"{max(0, rem_sec // 60):02d}:{max(0, rem_sec % 60):02d}", f"{elapsed_sec // 60:02d}:{elapsed_sec % 60:02d}"
    except: return "10:00", str(time_str)

# --- UI RENDERING FUNKTIONEN ---

def render_game_header(details):
    h_data, g_data = details.get("homeTeam", {}), details.get("guestTeam", {})
    h_name, g_name = get_team_name(h_data, "Heim"), get_team_name(g_data, "Gast")
    res = details.get("result", {})
    sh, sg = res.get("homeTeamFinalScore", 0), res.get("guestTeamFinalScore", 0)
    time_str = format_date_time(details.get("scheduledTime"))
    venue = details.get("venue", {})
    vs = f"{venue.get('name', '-')}, {venue.get('address', '').split(',')[-1].strip()}"
    st.markdown(f"<div style='text-align: center; color: #666;'>📍 {vs} | 🕒 {time_str}</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([2, 1, 2])
    c1.markdown(f"<h2 style='text-align:right;'>{h_name}</h2>", unsafe_allow_html=True)
    c2.markdown(f"<h1 style='text-align:center;'>{sh}:{sg}</h1>", unsafe_allow_html=True)
    c3.markdown(f"<h2 style='text-align:left;'>{g_name}</h2>", unsafe_allow_html=True)

def render_boxscore_table_pro(player_stats, team_stats_official, team_name, coach_name="-"):
    if not player_stats: return
    data = []
    s_pts=0; s_m2=0; s_a2=0; s_m3=0; s_a3=0; s_mf=0; s_af=0; s_mfg=0; s_afg=0
    s_or=0; s_dr=0; s_tr=0; s_as=0; s_st=0; s_to=0; s_bs=0; s_pf=0; s_eff=0; s_sec=0

    def fmt_stat(made, att):
        pct = safe_div(made, att)
        return f"{made}/{att} ({int(pct)}%)"

    for p in player_stats:
        info = p.get("seasonPlayer", {})
        sec = safe_int(p.get("secondsPlayed")); s_sec += sec
        pts = safe_int(p.get("points")); s_pts += pts
        m2, a2 = safe_int(p.get("twoPointShotsMade")), safe_int(p.get("twoPointShotsAttempted")); s_m2 += m2; s_a2 += a2
        m3, a3 = safe_int(p.get("threePointShotsMade")), safe_int(p.get("threePointShotsAttempted")); s_m3 += m3; s_a3 += a3
        mf, af = safe_int(p.get("freeThrowsMade")), safe_int(p.get("freeThrowsAttempted")); s_mf += mf; s_af += af
        fgm, fga = safe_int(p.get("fieldGoalsMade")), safe_int(p.get("fieldGoalsAttempted"))
        if fga == 0: fgm, fga = m2+m3, a2+a3
        s_mfg += fgm; s_afg += fga
        oreb, dreb, treb = safe_int(p.get("offensiveRebounds")), safe_int(p.get("defensiveRebounds")), safe_int(p.get("totalRebounds"))
        s_or += oreb; s_dr += dreb; s_tr += treb
        ast, stl, tov, blk, pf = safe_int(p.get("assists")), safe_int(p.get("steals")), safe_int(p.get("turnovers")), safe_int(p.get("blocks")), safe_int(p.get("foulsCommitted"))
        s_as += ast; s_st += stl; s_to += tov; s_bs += blk; s_pf += pf
        eff, pm = safe_int(p.get("efficiency")), safe_int(p.get("plusMinus")); s_eff += eff

        data.append({
            "#": str(info.get('shirtNumber', '-')), "Name": f"{info.get('lastName','-')}, {info.get('firstName','')}", 
            "Min": f"{sec//60:02d}:{sec%60:02d}", "PTS": pts, "2P": fmt_stat(m2, a2), "3P": fmt_stat(m3, a3), "FG": fmt_stat(fgm, fga), "FT": fmt_stat(mf, af),
            "OR": oreb, "DR": dreb, "TR": treb, "AS": ast, "ST": stl, "TO": tov, "BS": blk, "PF": pf, "EFF": eff, "+/-": pm
        })
    
    st.markdown(f"#### {team_name} (HC: {coach_name})")
    df = pd.DataFrame(data)
    st.dataframe(df, hide_index=True, width="stretch")

def render_charts_and_stats(box):
    st.markdown("### Team Statistik")
    render_live_comparison_bars(box)

def render_live_comparison_bars(box):
    h_stat = box.get("homeTeam", {}).get("gameStat", {})
    g_stat = box.get("guestTeam", {}).get("gameStat", {})
    h_name, g_name = get_team_name(box.get("homeTeam", {})), get_team_name(box.get("guestTeam", {}))
    
    stats_to_show = [
        ("2 PUNKTE", "twoPointShotsMade", "twoPointShotsAttempted", True), 
        ("3 PUNKTE", "threePointShotsMade", "threePointShotsAttempted", True), 
        ("FIELDGOALS", "fieldGoalsMade", "fieldGoalsAttempted", True), 
        ("FREIWÜRFE", "freeThrowsMade", "freeThrowsAttempted", True), 
        ("DEF. REBOUNDS", "defensiveRebounds", None, False), 
        ("OFF. REBOUNDS", "offensiveRebounds", None, False), 
        ("REBOUNDS", "totalRebounds", None, False), 
        ("ASSISTS", "assists", None, False), 
        ("STEALS", "steals", None, False), 
        ("BLOCKS", "blocks", None, False), 
        ("TURNOVERS", "turnovers", None, False), 
        ("FOULS", "foulsCommitted", None, False)
    ]
    
    for label, km, ka, is_p in stats_to_show:
        hv, gv = safe_int(h_stat.get(km)), safe_int(g_stat.get(km))
        if is_p:
            ha, ga = safe_int(h_stat.get(ka)), safe_int(g_stat.get(ka))
            hp, gp = safe_div(hv, ha), safe_div(gv, ga)
            hd, gd = f"{hp}% ({hv}/{ha})", f"{gp}% ({gv}/{ga})"
            hf, gf = hp, gp
        else:
            hd, gd = str(hv), str(gv)
            mv = max(hv, gv, 1)
            hf, gf = (hv/mv)*100, (gv/mv)*100
        
        st.write(f"**{label}**")
        c1, c2, c3 = st.columns([1, 4, 1])
        c1.write(hd)
        c2.progress(hf/100 if hf > gf else gf/100) # Vereinfachter Progressbar
        c3.write(gd)

def render_full_play_by_play(box, height=600):
    actions = box.get("actions", [])
    if not actions: st.info("Keine Play-by-Play Daten verfügbar."); return
    player_map = get_player_lookup(box); team_map = get_player_team_map(box)
    h_name, g_name = get_team_name(box.get("homeTeam")), get_team_name(box.get("guestTeam"))
    h_ids, g_ids = get_team_ids(box.get("homeTeam", {})), get_team_ids(box.get("guestTeam", {}))
    
    data = []; run_h, run_g = 0, 0
    actions_sorted = sorted(actions, key=lambda x: x.get('actionNumber', 0))
    for act in actions_sorted:
        hr, gr = act.get("homeTeamPoints"), act.get("guestTeamPoints")
        if hr is not None and gr is not None: run_h, run_g = safe_int(hr), safe_int(gr)
        p = act.get("period", "")
        t_rem, t_orig = get_time_info(act.get("gameTime") or act.get("timeInGame"), p)
        pid = str(act.get("seasonPlayerId"))
        team = team_map.get(pid) or (h_name if str(act.get("seasonTeamId")) in h_ids else (g_name if str(act.get("seasonTeamId")) in g_ids else "-"))
        actor = player_map.get(pid, ""); desc = translate_text(act.get("type"))
        if act.get("points"): desc += f" (+{act.get('points')})"
        data.append({"Zeit": f"Q{p} | {t_rem}", "Score": f"{run_h}:{run_g}", "Team": team, "Spieler": actor, "Aktion": desc})
    
    df = pd.DataFrame(data).iloc[::-1]
    st.dataframe(df, width="stretch", hide_index=True, height=height)

def render_prep_dashboard(team_id, team_name, df_roster, last_games, metadata_callback=None):
    st.subheader(f"Analyse: {team_name}")
    # Hier Dashboard Logik...
    st.write("Vorbereitungs-Daten werden geladen...")

def render_live_view(box):
    if not box: return
    render_game_header(box)
    st.divider()
    t1, t2 = st.tabs(["📊 Team-Statistik", "📜 Play-by-Play"])
    with t1: render_charts_and_stats(box)
    with t2: render_full_play_by_play(box)

def generate_game_summary(box):
    h, g = get_team_name(box.get("homeTeam")), get_team_name(box.get("guestTeam"))
    res = box.get("result", {})
    return f"Spiel zwischen {h} und {g}. Endstand {res.get('homeTeamFinalScore',0)}:{res.get('guestTeamFinalScore',0)}."

def generate_complex_ai_prompt(box):
    return f"KI-Analyse für Game {box.get('id')}"

def run_openai_generation(api_key, prompt):
    return "KI-Service nicht konfiguriert."

# --- SCOUTING & ANALYSIS ---

def analyze_scouting_data(team_id, detailed_games):
    stats = { "games_count": len(detailed_games), "wins": 0, "top_scorers_list": [] }
    return stats

def render_team_analysis_dashboard(team_id, team_name):
    st.title(f"Scouting: {team_name}")
    games = fetch_last_n_games_complete(team_id, "2025", n=5)
    if games:
        st.success(f"{len(games)} Spiele analysiert.")
    else:
        st.warning("Keine Daten für dieses Team gefunden.")

# --- PAGE WRAPPERS FOR APP.PY ---

def render_team_analysis_page():
    team_id = st.session_state.get("selected_team_id")
    team_name = st.session_state.get("selected_team_name", "Team")
    if not team_id:
        st.info("Bitte wählen Sie im Hauptmenü ein Team aus.")
        return
    render_team_analysis_dashboard(team_id, team_name)

def render_game_venue_page():
    st.title("Spielort Details")
    game_id = st.session_state.get("selected_game_id")
    if not game_id:
        st.info("Kein Spiel ausgewählt.")
        return
    st.write(f"Informationen zum Austragungsort für Spiel {game_id}")

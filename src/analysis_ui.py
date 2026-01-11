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
    """Berechnet (Restzeit, Originalzeit)"""
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

# --- CORE LOGIC ---

def analyze_game_flow(actions, home_name, guest_name):
    if not actions: return "Keine Play-by-Play Daten verfügbar."
    lead_changes, ties = 0, 0
    last_leader = None
    sorted_actions = sorted(actions, key=lambda x: x.get('actionNumber', 0))
    for act in sorted_actions:
        h, g = safe_int(act.get("homeTeamPoints")), safe_int(act.get("guestTeamPoints"))
        if h == 0 and g == 0: continue
        current_leader = 'home' if h > g else ('guest' if g > h else 'tie')
        if last_leader is not None and current_leader != last_leader:
            if current_leader == 'tie': ties += 1
            else: lead_changes += 1
        last_leader = current_leader
    rel_types = ["TWO_POINT_SHOT_MADE", "THREE_POINT_SHOT_MADE", "FREE_THROW_MADE", "TURNOVER", "FOUL", "TIMEOUT"]
    filtered = [a for a in sorted_actions if a.get("type") in rel_types]
    last_events = filtered[-20:] 
    crunch = "\n**⏱️ Die Schlussphase (Chronologie der letzten Ereignisse):**"
    for ev in last_events:
        score = f"{ev.get('homeTeamPoints')}:{ev.get('guestTeamPoints')}"
        desc = translate_text(ev.get("type", ""))
        if ev.get("points"): desc += f" (+{ev.get('points')})"
        crunch += f"\n- {score}: {desc}"
    return f"Führungswechsel: {lead_changes}, Unentschieden: {ties}.{crunch}"

# --- ANALYSIS SEITE FUNKTIONEN ---

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
    for p in player_stats:
        info = p.get("seasonPlayer", {})
        sec = safe_int(p.get("secondsPlayed"))
        m2, a2 = safe_int(p.get("twoPointShotsMade")), safe_int(p.get("twoPointShotsAttempted"))
        m3, a3 = safe_int(p.get("threePointShotsMade")), safe_int(p.get("threePointShotsAttempted"))
        data.append({"#": info.get('shirtNumber','-'), "Name": info.get('lastName','-'), "Min": f"{sec//60:02d}:{sec%60:02d}", "PTS": safe_int(p.get("points")), "FG": f"{m2+m3}/{a2+a3}", "3P": f"{m3}/{a3}", "REB": safe_int(p.get("totalRebounds")), "AS": safe_int(p.get("assists")), "TO": safe_int(p.get("turnovers")), "PF": safe_int(p.get("foulsCommitted")), "+/-": safe_int(p.get("plusMinus"))})
    df = pd.DataFrame(data)
    st.markdown(f"#### {team_name} (HC: {coach_name})")
    st.dataframe(df, hide_index=True, use_container_width=True, height=(len(df)+1)*35+3)

def render_game_top_performers(box):
    st.markdown("### Top Performer")
    c1, c2 = st.columns(2)
    for i, team_key in enumerate(["homeTeam", "guestTeam"]):
        td = box.get(team_key, {})
        players = sorted([p for p in td.get("playerStats", [])], key=lambda x: safe_int(x.get("points")), reverse=True)[:3]
        with [c1, c2][i]:
            st.write(f"**{get_team_name(td)}**")
            for p in players: st.write(f"{p.get('seasonPlayer',{}).get('lastName')}: {p.get('points')} Pkt")

def render_charts_and_stats(box):
    st.markdown("### Team Statistik")
    render_live_comparison_bars(box)

def generate_game_summary(box):
    h, g = get_team_name(box.get("homeTeam")), get_team_name(box.get("guestTeam"))
    res = box.get("result", {})
    return f"Spiel zwischen {h} und {g}. Endstand {res.get('homeTeamFinalScore',0)}:{res.get('guestTeamFinalScore',0)}."

def generate_complex_ai_prompt(box):
    if not box: return "Keine Daten."
    h_data, g_data = box.get("homeTeam", {}), box.get("guestTeam", {})
    h_name, g_name = get_team_name(h_data), get_team_name(g_data)
    res = box.get("result", {})
    pbp_summary = analyze_game_flow(box.get("actions", []), h_name, g_name)
    is_home_jena = "Jena" in h_name or "VIMODROM" in h_name
    opponent = g_name if is_home_jena else (h_name if "Jena" in g_name or "VIMODROM" in g_name else f"{h_name} vs {g_name}")
    location = "Heimspiel" if is_home_jena else ("Auswärtsspiel" if "Jena" in g_name or "VIMODROM" in g_name else "Neutral")
    def get_stats_str(td):
        s = td.get("gameStat", {})
        p_list = td.get("playerStats", [])
        top_p = sorted([p for p in p_list if p.get("points", 0) is not None], key=lambda x: x.get("points", 0), reverse=True)[:3]
        top_str = ", ".join([f"{p.get('seasonPlayer', {}).get('lastName')} ({p.get('points')})" for p in top_p])
        return f"FG: {safe_int(s.get('fieldGoalsSuccessPercent'))}%, Reb: {safe_int(s.get('totalRebounds'))}, TO: {safe_int(s.get('turnovers'))}. Top: {top_str}"
    
    prompt = f"""Du agierst als erfahrener Sportjournalist. Erstelle 3 Artikel & einen Storytelling-Bericht gegen {opponent}.\nErgebnis: {h_name} {res.get('homeTeamFinalScore')} : {res.get('guestTeamFinalScore')} {g_name}.\nOrt: {location} in {box.get('venue', {}).get('name', 'Halle')}.\nStats {h_name}: {get_stats_str(h_data)}.\nStats {g_name}: {get_stats_str(g_data)}.\nPBP-Analyse: {pbp_summary}"""
    return prompt

def run_openai_generation(api_key, prompt):
    client = openai.OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
        return response.choices[0].message.content
    except Exception as e: return str(e)

# --- LIVE VIEW & TICKER ---

def render_live_comparison_bars(box):
    h_stat = box.get("homeTeam", {}).get("gameStat", {})
    g_stat = box.get("guestTeam", {}).get("gameStat", {})
    h_name, g_name = get_team_name(box.get("homeTeam", {})), get_team_name(box.get("guestTeam", {}))
    def get_pct(made, att):
        m, a = safe_int(made), safe_int(att)
        return round((m / a * 100), 1) if a > 0 else 0.0
    stats_to_show = [("2 PUNKTE", "twoPointShotsMade", "twoPointShotsAttempted", True), ("3 PUNKTE", "threePointShotsMade", "threePointShotsAttempted", True), ("FIELDGOALS", "fieldGoalsMade", "fieldGoalsAttempted", True), ("FREIWÜRFE", "freeThrowsMade", "freeThrowsAttempted", True), ("DEF. REBOUNDS", "defensiveRebounds", None, False), ("OFF. REBOUNDS", "offensiveRebounds", None, False), ("ASSISTS", "assists", None, False), ("STEALS", "steals", None, False), ("BLOCKS", "blocks", None, False), ("TURNOVERS", "turnovers", None, False), ("FOULS", "foulsCommitted", None, False)]
    st.markdown("""<style>.stat-container { margin-bottom: 12px; width: 100%; }.stat-label { text-align: center; font-weight: bold; font-style: italic; color: #555; font-size: 0.85em; }.bar-wrapper { display: flex; align-items: center; justify-content: center; gap: 8px; height: 10px; }.bar-bg { background-color: #eee; flex-grow: 1; height: 100%; border-radius: 2px; position: relative; }.bar-fill-home { background-color: #e35b00; height: 100%; position: absolute; right: 0; }.bar-fill-guest { background-color: #333; height: 100%; position: absolute; left: 0; }.val-text { width: 85px; font-weight: bold; font-size: 0.85em; }</style>""", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    c1.markdown(f"<h4 style='text-align:right; color:#e35b00;'>{h_name}</h4>", unsafe_allow_html=True)
    c3.markdown(f"<h4 style='text-align:left; color:#333;'>{g_name}</h4>", unsafe_allow_html=True)
    for label, km, ka, is_p in stats_to_show:
        hv, gv = safe_int(h_stat.get(km)), safe_int(g_stat.get(km))
        if is_p:
            ha, ga = safe_int(h_stat.get(ka)), safe_int(g_stat.get(ka))
            hp, gp = get_pct(hv, ha), get_pct(gv, ga)
            hd, gd, hf, gf = f"{hp}%", f"{gp}%", hp, gp
        else:
            hd, gd = str(hv), str(gv)
            mv = max(hv, gv, 1)
            hf, gf = (hv/mv)*100, (gv/mv)*100
        st.markdown(f"""<div class="stat-container"><div class="stat-label">{label}</div><div class="bar-wrapper"><div class="val-text" style="text-align:right;">{hd}</div><div class="bar-bg"><div class="bar-fill-home" style="width:{hf}%;"></div></div><div class="bar-bg"><div class="bar-fill-guest" style="width:{gf}%;"></div></div><div class="val-text" style="text-align:left;">{gd}</div></div></div>""", unsafe_allow_html=True)

def render_full_play_by_play(box, height=600):
    actions = box.get("actions", [])
    if not actions: st.info("Keine Play-by-Play Daten verfügbar."); return
    player_map = get_player_lookup(box); player_team_map = get_player_team_map(box)
    h_name, g_name = get_team_name(box.get("homeTeam")), get_team_name(box.get("guestTeam"))
    
    # IDs sammeln für Fallback
    h_ids = [str(box.get("homeTeam",{}).get("seasonTeamId")), str(box.get("homeTeam",{}).get("teamId")), str(box.get("homeTeam", {}).get("seasonTeam", {}).get("id"))]
    g_ids = [str(box.get("guestTeam",{}).get("seasonTeamId")), str(box.get("guestTeam",{}).get("teamId")), str(box.get("guestTeam", {}).get("seasonTeam", {}).get("id"))]
    
    data = []
    run_h, run_g = 0, 0
    actions_sorted = sorted(actions, key=lambda x: x.get('actionNumber', 0))
    for act in actions_sorted:
        hr, gr = act.get("homeTeamPoints"), act.get("guestTeamPoints")
        if hr is not None and gr is not None:
            nh, ng = safe_int(hr), safe_int(gr)
            if (nh + ng) >= (run_h + run_g): run_h, run_g = nh, ng
        p = act.get("period", "")
        t_rem, t_orig = get_time_info(act.get("gameTime") or act.get("timeInGame"), p)
        pid = str(act.get("seasonPlayerId"))
        team = player_team_map.get(pid)
        if not team:
            tid = str(act.get("seasonTeamId"))
            team = h_name if tid in h_ids else (g_name if tid in g_ids else "-")
        actor = player_map.get(pid, ""); desc = translate_text(act.get("type", ""))
        if act.get("points"): desc += f" (+{act.get('points')})"
        data.append({"Zeit": f"Q{p} | {t_rem} ({t_orig})", "Score": f"{run_h}:{run_g}", "Team": team, "Spieler": actor, "Aktion": desc})
    df = pd.DataFrame(data)
    if not df.empty: df = df.iloc[::-1]
    st.dataframe(df, use_container_width=True, hide_index=True, height=height)

def render_live_view(box):
    if not box: return
    h_data, g_data = box.get("homeTeam", {}), box.get("guestTeam", {})
    h_name, g_name = get_team_name(h_data), get_team_name(g_data)
    res = box.get("result", {}); sh, sg = safe_int(res.get('homeTeamFinalScore')), safe_int(res.get('guestTeamFinalScore'))
    period = res.get('period') or box.get('period')
    actions = box.get("actions", [])
    if sh == 0 and sg == 0 and actions:
        last = sorted(actions, key=lambda x: x.get('actionNumber', 0))[-1]
        sh, sg = safe_int(last.get('homeTeamPoints')), safe_int(last.get('guestTeamPoints'))
        if not period: period = last.get('period')
    p_map = {1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"}
    if not period or period == 0:
        for act in reversed(actions):
            if act.get('period'): period = act.get('period'); break
    p_str = (f"OT{safe_int(period)-4}" if safe_int(period) > 4 else p_map.get(safe_int(period), f"Q{period}")) if period else "-"
    gt = box.get('gameTime') or (actions[-1].get('gameTime') if actions else None)
    t_rem, t_orig = get_time_info(gt, period)
    h_hc = h_data.get("headCoachName") or h_data.get("headCoach",{}).get("lastName","-")
    g_hc = g_data.get("headCoachName") or g_data.get("headCoach",{}).get("lastName","-")
    st.markdown(f"<div style='text-align:center;background:#222;color:#fff;padding:15px;border-radius:10px;margin-bottom:20px;'><div style='font-size:1.4em; font-weight:bold;'>{h_name} <span style='font-size:0.6em; color:#aaa;'>(HC: {h_hc})</span></div><div style='font-size:3.5em; font-weight:bold; line-height:1;'>{sh} : {sg}</div><div style='font-size:1.4em; font-weight:bold;'>{g_name} <span style='font-size:0.6em; color:#aaa;'>(HC: {g_hc})</span></div><div style='color:#ffcc00; font-weight:bold; font-size:2em; margin-top:10px;'>{p_str} | {t_rem} <span style='font-size:0.5em; color:#fff;'> (gespielt {t_orig})</span></div></div>", unsafe_allow_html=True)
    t1, t2, t3 = st.tabs(["📋 Boxscore", "📊 Team-Vergleich", "📜 Play-by-Play"])
    with t1:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"### {h_name}")
            dfh = create_live_boxscore_df(h_data)
            if not dfh.empty: st.dataframe(dfh, hide_index=True, use_container_width=True, height=(len(dfh)+1)*35+3)
        with c2:
            st.markdown(f"### {g_name}")
            dfg = create_live_boxscore_df(g_data)
            if not dfg.empty: st.dataframe(dfg, hide_index=True, use_container_width=True, height=(len(dfg)+1)*35+3)
    with t2: render_live_comparison_bars(box)
    with t3: render_full_play_by_play(box)

def create_live_boxscore_df(team_data):
    stats = []
    for p in team_data.get("playerStats", []):
        sec = safe_int(p.get("secondsPlayed"))
        m2, a2 = safe_int(p.get("twoPointShotsMade")), safe_int(p.get("twoPointShotsAttempted"))
        m3, a3 = safe_int(p.get("threePointShotsMade")), safe_int(p.get("threePointShotsAttempted"))
        stats.append({"#": p.get("seasonPlayer",{}).get("shirtNumber","-"), "Name": p.get("seasonPlayer",{}).get("lastName","Unk"), "Min": f"{sec // 60:02d}:{sec % 60:02d}", "PTS": safe_int(p.get("points")), "FG": f"{m2+m3}/{a2+a3}", "3P": f"{m3}/{a3}", "TR": safe_int(p.get("totalRebounds")), "AS": safe_int(p.get("assists")), "TO": safe_int(p.get("turnovers")), "PF": safe_int(p.get("foulsCommitted")), "+/-": safe_int(p.get("plusMinus")), "OnCourt": p.get("onCourt", False) or p.get("isOnCourt", False)})
    df = pd.DataFrame(stats)
    return df.sort_values(by=["PTS", "Min"], ascending=[False, False]) if not df.empty else df

# --- PREP & SCOUTING (Team-Analyse) ---

def render_prep_dashboard(team_id, team_name, df_roster, last_games, metadata_callback=None):
    st.subheader(f"Analyse: {team_name}")
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown("#### Top 4 Spieler")
        if df_roster is not None and not df_roster.empty:
            top4 = df_roster.sort_values(by="PPG", ascending=False).head(4)
            for _, row in top4.iterrows():
                with st.container(border=True):
                    ci, cs = st.columns([1, 4])
                    img = metadata_callback(row["PLAYER_ID"]).get("img") if metadata_callback else None
                    if img: ci.image(img, width=80)
                    else: ci.markdown("<div style='font-size:30px;'>👤</div>", unsafe_allow_html=True)
                    cs.markdown(f"**#{row.get('NR','-')} {row.get('NAME_FULL','Unk')}**")
                    cs.markdown(f"**{row.get('PPG',0)} PPG** | FG: {row.get('FG%',0)}% | 3P: {row.get('3PCT',0)}%")
    with c2:
        st.markdown("#### Formkurve")
        for g in last_games[:5]:
            with st.container(border=True):
                st.caption(f"{g.get('date','').split(' ')[0]}")
                st.write(f"vs {g.get('home') if team_name not in g.get('home') else g.get('guest')}")
                st.write(f"**{g.get('score')}**")

def analyze_scouting_data(team_id, detailed_games):
    stats = { "games_count": len(detailed_games), "wins": 0, "ato_stats": {"possessions": 0, "points": 0}, "start_stats": {"pts_diff_first_5min": 0}, "top_scorers": {}, "rotation_depth": 0 }
    tid_str = str(team_id)
    for box in detailed_games:
        is_h = box.get('meta_is_home', False); sh, sg = safe_int(box.get("result",{}).get("homeTeamFinalScore") or box.get("homeTeamPoints")), safe_int(box.get("result",{}).get("guestTeamFinalScore") or box.get("guestTeamPoints"))
        if (is_h and sh > sg) or (not is_h and sg > sh): stats["wins"] += 1
        to = box.get("homeTeam") if is_h else box.get("guestTeam")
        if to:
            act_p = 0
            for p in to.get("playerStats", []):
                pid = p.get("seasonPlayer",{}).get("id"); pts, sec = safe_int(p.get("points")), safe_int(p.get("secondsPlayed"))
                if sec > 300: act_p += 1
                if pid not in stats["top_scorers"]: stats["top_scorers"][pid] = {"name": p.get("seasonPlayer",{}).get("lastName","Unk"), "pts": 0, "games": 0}
                stats["top_scorers"][pid]["pts"] += pts; stats["top_scorers"][pid]["games"] += 1
            stats["rotation_depth"] += act_p
        actions = sorted(box.get("actions", []), key=lambda x: x.get('actionNumber', 0))
        hs, gs = 0, 0
        for act in actions:
            if act.get("period") != 1: break
            if act.get("homeTeamPoints") is not None: hs, gs = safe_int(act.get("homeTeamPoints")), safe_int(act.get("guestTeamPoints"))
            if safe_int(act.get("actionNumber")) > 25: break 
        stats["start_stats"]["pts_diff_first_5min"] += (hs - gs if is_h else gs - hs)
    cnt = stats["games_count"] or 1
    stats["rotation_depth"] = round(stats["rotation_depth"]/cnt, 1); stats["start_stats"]["avg_diff"] = round(stats["start_stats"]["pts_diff_first_5min"]/cnt, 1)
    scorer = [{"name": d["name"], "ppg": round(d["pts"]/d["games"], 1)} for d in stats["top_scorers"].values() if d["games"] > 0]
    stats["top_scorers_list"] = sorted(scorer, key=lambda x: x["ppg"], reverse=True)[:5]
    return stats

def prepare_ai_scouting_context(team_name, detailed_games, team_id):
    ctx = f"Scouting-Daten für {team_name}\nAnzahl Spiele: {len(detailed_games)}\n\n"
    for g in detailed_games:
        is_h = g.get('meta_is_home', False); mysid = str(g.get("homeTeam" if is_h else "guestTeam", {}).get("seasonTeamId"))
        ctx += f"--- Spiel vs {g.get('meta_opponent')} ({g.get('meta_result')}) ---\n"; pmap = get_player_lookup(g)
        starters = [pmap.get(str(p.get("seasonPlayer",{}).get("id")), "Unk") for p in g.get("homeTeam" if is_h else "guestTeam", {}).get("playerStats", []) if p.get("isStartingFive")]
        ctx += f"Starter: {', '.join(starters)}\n"; actions = sorted(g.get("actions", []), key=lambda x: x.get('actionNumber', 0))
        ctx += "Start Phase Q1:\n"
        for act in actions[:12]:
            tid = str(act.get("seasonTeamId")); actor = "WIR" if tid == mysid else "GEGNER"
            pn = pmap.get(str(act.get("seasonPlayerId")), ""); desc = translate_text(act.get("type", ""))
            ctx += f"- {actor}{' ('+pn+')' if pn and actor=='WIR' else ''}: {desc} {act.get('points','')}Pkt\n"
        ctx += "ATO:\n"
        for i, act in enumerate(actions):
            if "TIMEOUT" in str(act.get("type")).upper() and str(act.get("seasonTeamId")) == mysid:
                ctx += "TIMEOUT (WIR). Next:\n"
                for j in range(1, 5):
                    if i+j < len(actions):
                        na = actions[i+j]; who = "WIR" if str(na.get("seasonTeamId")) == mysid else "GEGNER"
                        ctx += f"  -> {who}: {translate_text(na.get('type',''))} {na.get('points','')}Pkt\n"
        ctx += "\n"
    return ctx

def render_team_analysis_dashboard(team_id, team_name):
    logo = get_best_team_logo(team_id); c1, c2 = st.columns([1, 4])
    if logo: c1.image(logo, width=100)
    c2.title(f"Scouting Report: {team_name}")
    with st.spinner("Analysiere..."):
        games = fetch_last_n_games_complete(team_id, "2025", n=50)
        if not games: st.warning("Keine Daten."); return
        scout = analyze_scouting_data(team_id, games)
    k1, k2, k3, k4 = st.columns(4); k1.metric("Spiele", scout["games_count"], f"{scout['wins']} Siege"); k2.metric("Start Q1", f"{scout['start_stats']['avg_diff']:+.1f}"); k3.metric("Rotation", scout["rotation_depth"])
    st.divider(); col_l, col_r = st.columns([1, 1])
    with col_l:
        st.subheader("🔑 Schlüsselspieler")
        if scout["top_scorers_list"]: st.dataframe(pd.DataFrame(scout["top_scorers_list"]), hide_index=True, use_container_width=True)
        st.markdown("---"); st.subheader("🤖 KI-Prompt"); st.code(f"Du bist ein professioneller Basketball-Scout. Analysiere {team_name}...\n\n{prepare_ai_scouting_context(team_name, games, team_id)}", language="text")
    with col_r:
        st.subheader("📅 Spiele")
        for g in games:
            with st.expander(f"{g.get('meta_date')} vs {g.get('meta_opponent')} ({g.get('meta_result')})"): st.caption(analyze_game_flow(g.get("actions", []), "Heim", "Gast"))

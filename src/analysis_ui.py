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
    "offensive": "Off", "defensive": "Def"
}

def translate_text(text):
    if not text: return ""
    text_upper = str(text).upper()
    if text_upper in ACTION_TRANSLATION: return ACTION_TRANSLATION[text_upper]
    return text.replace("_", " ").title()

def safe_int(val):
    if val is None: return 0
    try: return int(float(val))
    except: return 0

def get_team_name(team_data, default_name="Team"):
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

def convert_elapsed_to_remaining(time_str, period):
    """Berechnet die Restzeit (Countdown) von 10:00 abwärts."""
    if not time_str: return "10:00"
    base_min = 5 if safe_int(period) > 4 else 10
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
        return f"{rem_sec // 60:02d}:{rem_sec % 60:02d}"
    except: return "10:00"

# --- VISUELLE STATISTIK-BALKEN ---

def render_live_comparison_bars(box):
    h_stat = box.get("homeTeam", {}).get("gameStat", {})
    g_stat = box.get("guestTeam", {}).get("gameStat", {})
    h_name = get_team_name(box.get("homeTeam", {}))
    g_name = get_team_name(box.get("guestTeam", {}))

    def get_pct(made, att):
        m = safe_int(made); a = safe_int(att)
        return round((m / a * 100), 1) if a > 0 else 0.0

    stats_to_show = [
        ("2 PUNKTE", "twoPointShotsMade", "twoPointShotsAttempted", True),
        ("3 PUNKTE", "threePointShotsMade", "threePointShotsAttempted", True),
        ("FIELDGOALS", "fieldGoalsMade", "fieldGoalsAttempted", True),
        ("FREIWÜRFE", "freeThrowsMade", "freeThrowsAttempted", True),
        ("DEF. REBOUNDS", "defensiveRebounds", None, False),
        ("OFF. REBOUNDS", "offensiveRebounds", None, False),
        ("ASSISTS", "assists", None, False),
        ("STEALS", "steals", None, False),
        ("BLOCKS", "blocks", None, False),
        ("TURNOVERS", "turnovers", None, False),
        ("FOULS", "foulsCommitted", None, False),
    ]

    st.markdown("""
        <style>
        .stat-container { margin-bottom: 15px; width: 100%; }
        .stat-label { text-align: center; font-weight: bold; font-style: italic; color: #555; font-size: 0.9em; }
        .bar-wrapper { display: flex; align-items: center; justify-content: center; gap: 10px; height: 12px; }
        .bar-bg { background-color: #eee; flex-grow: 1; height: 100%; border-radius: 2px; position: relative; }
        .bar-fill-home { background-color: #e35b00; height: 100%; position: absolute; right: 0; }
        .bar-fill-guest { background-color: #333; height: 100%; position: absolute; left: 0; }
        .val-text { width: 90px; font-weight: bold; font-size: 0.9em; }
        .sub-val { font-size: 0.8em; color: #888; font-weight: normal; }
        </style>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 1, 1])
    c1.markdown(f"<h4 style='text-align:right; color:#e35b00;'>{h_name}</h4>", unsafe_allow_html=True)
    c3.markdown(f"<h4 style='text-align:left; color:#333;'>{g_name}</h4>", unsafe_allow_html=True)

    for label, key_made, key_att, is_pct in stats_to_show:
        h_v = safe_int(h_stat.get(key_made))
        g_v = safe_int(g_stat.get(key_made))
        if is_pct:
            h_a = safe_int(h_stat.get(key_att))
            g_a = safe_int(g_stat.get(key_att))
            h_p = get_pct(h_v, h_a); g_p = get_pct(g_v, g_a)
            h_d = f"{h_p}% <span class='sub-val'>({h_v}/{h_a})</span>"
            g_d = f"{g_p}% <span class='sub-val'>({g_v}/{g_a})</span>"
            h_fill, g_fill = h_p, g_p
        else:
            h_d, g_d = str(h_v), str(g_v)
            max_v = max(h_v, g_v, 1)
            h_fill, g_fill = (h_v/max_v)*100, (g_v/max_v)*100

        st.markdown(f"""
            <div class="stat-container">
                <div class="stat-label">{label}</div>
                <div class="bar-wrapper">
                    <div class="val-text" style="text-align:right;">{h_d}</div>
                    <div class="bar-bg"><div class="bar-fill-home" style="width:{h_fill}%;"></div></div>
                    <div class="bar-bg"><div class="bar-fill-guest" style="width:{g_fill}%;"></div></div>
                    <div class="val-text" style="text-align:left;">{g_d}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

# --- ANALYSIS SEITE FUNKTIONEN (MÜSSEN FÜR APP.PY DA SEIN) ---

def render_game_header(details):
    h_data, g_data = details.get("homeTeam", {}), details.get("guestTeam", {})
    h_name, g_name = get_team_name(h_data, "Heim"), get_team_name(g_data, "Gast")
    res = details.get("result", {})
    score_h, score_g = res.get("homeTeamFinalScore", 0), res.get("guestTeamFinalScore", 0)
    time_str = format_date_time(details.get("scheduledTime"))
    venue = details.get("venue", {})
    venue_str = f"{venue.get('name', '-')}, {venue.get('address', '').split(',')[-1].strip()}"
    refs = []
    for i in range(1, 4):
        r = details.get(f"referee{i}")
        if r and isinstance(r, dict): refs.append(f"{r.get('lastName')} {r.get('firstName')}")
    ref_str = ", ".join(refs) if refs else "-"
    st.markdown(f"<div style='text-align: center; color: #666; font-size: 1.1em;'>📍 {venue_str} | 🕒 {time_str}</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([2, 1, 2])
    with c1: st.markdown(f"## {h_name}")
    with c2:
        st.markdown(f"<h1 style='text-align: center;'>{score_h} : {score_g}</h1>", unsafe_allow_html=True)
    with c3: st.markdown(f"## {g_name}")
    st.markdown(f"<div style='text-align:center; font-size:0.8em; color:#888;'>Refs: {ref_str} | ID: {details.get('id','-')}</div>", unsafe_allow_html=True)

def render_boxscore_table_pro(player_stats, team_stats_official, team_name, coach_name="-"):
    if not player_stats: return
    data = []
    for p in player_stats:
        info = p.get("seasonPlayer", {})
        name = f"{info.get('lastName', '')}, {info.get('firstName', '')}"
        nr = info.get("shirtNumber", "-")
        sec = safe_int(p.get("secondsPlayed"))
        pts = safe_int(p.get("points"))
        m2, a2 = safe_int(p.get("twoPointShotsMade")), safe_int(p.get("twoPointShotsAttempted"))
        m3, a3 = safe_int(p.get("threePointShotsMade")), safe_int(p.get("threePointShotsAttempted"))
        data.append({"#": nr, "Name": name, "Min": f"{sec//60:02d}:{sec%60:02d}", "PTS": pts, "FG": f"{m2+m3}/{a2+a3}", "3P": f"{m3}/{a3}", "REB": safe_int(p.get("totalRebounds")), "AS": safe_int(p.get("assists")), "TO": safe_int(p.get("turnovers")), "PF": safe_int(p.get("foulsCommitted")), "+/-": safe_int(p.get("plusMinus"))})
    df = pd.DataFrame(data)
    st.markdown(f"#### {team_name} (HC: {coach_name})")
    st.dataframe(df, hide_index=True, use_container_width=True, height=(len(df)+1)*35+3)

def render_game_top_performers(box):
    st.markdown("### Top Performer")
    c1, c2 = st.columns(2)
    for i, team_key in enumerate(["homeTeam", "guestTeam"]):
        t_data = box.get(team_key, {})
        players = sorted([p for p in t_data.get("playerStats", []) if safe_int(p.get("points")) > 0], key=lambda x: safe_int(x.get("points")), reverse=True)[:3]
        with [c1, c2][i]:
            st.write(f"**{get_team_name(t_data)}**")
            for p in players: st.write(f"{p.get('seasonPlayer',{}).get('lastName')}: {p.get('points')} Pkt")

def render_charts_and_stats(box):
    st.markdown("### Team Statistik")
    render_live_comparison_bars(box)

def generate_game_summary(box):
    h, g = get_team_name(box.get("homeTeam")), get_team_name(box.get("guestTeam"))
    res = box.get("result", {})
    return f"Spiel zwischen {h} und {g}. Endstand {res.get('homeTeamFinalScore')}:{res.get('guestTeamFinalScore')}."

def generate_complex_ai_prompt(box):
    return "Hier ist ein Platzhalter für den Prompt..."

def run_openai_generation(api_key, prompt):
    client = openai.OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
        return response.choices[0].message.content
    except Exception as e: return str(e)

# --- LIVE VIEW ---

def create_live_boxscore_df(team_data):
    stats = []
    for p in team_data.get("playerStats", []):
        sec = safe_int(p.get("secondsPlayed"))
        m2, a2 = safe_int(p.get("twoPointShotsMade")), safe_int(p.get("twoPointShotsAttempted"))
        m3, a3 = safe_int(p.get("threePointShotsMade")), safe_int(p.get("threePointShotsAttempted"))
        mf, af = safe_int(p.get("freeThrowsMade")), safe_int(p.get("freeThrowsAttempted"))
        stats.append({
            "#": p.get("seasonPlayer", {}).get("shirtNumber", "-"),
            "Name": p.get("seasonPlayer", {}).get("lastName", "Unk"),
            "Min": f"{sec // 60:02d}:{sec % 60:02d}",
            "PTS": safe_int(p.get("points")),
            "FG": f"{m2+m3}/{a2+a3}", "3P": f"{m3}/{a3}", "FT": f"{mf}/{af}",
            "TR": safe_int(p.get("totalRebounds")), "AS": safe_int(p.get("assists")),
            "TO": safe_int(p.get("turnovers")), "PF": safe_int(p.get("foulsCommitted")),
            "+/-": safe_int(p.get("plusMinus")),
            "OnCourt": p.get("onCourt", False) or p.get("isOnCourt", False)
        })
    df = pd.DataFrame(stats)
    return df.sort_values(by=["PTS", "Min"], ascending=[False, False]) if not df.empty else df

def render_live_view(box):
    if not box: return
    h_data, g_data = box.get("homeTeam", {}), box.get("guestTeam", {})
    h_name, g_name = get_team_name(h_data), get_team_name(g_data)
    res = box.get("result", {})
    s_h, s_g = safe_int(res.get('homeTeamFinalScore')), safe_int(res.get('guestTeamFinalScore'))
    period = res.get('period') or box.get('period')
    actions = box.get("actions", [])
    if s_h == 0 and s_g == 0 and actions:
        last = actions[-1]
        s_h, s_g = safe_int(last.get('homeTeamPoints')), safe_int(last.get('guestTeamPoints'))
        if not period: period = last.get('period')
    p_map = {1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"}
    if not period or period == 0:
        for act in reversed(actions):
            if act.get('period'): period = act.get('period'); break
    p_str = (f"OT{safe_int(period)-4}" if safe_int(period) > 4 else p_map.get(safe_int(period), f"Q{period}")) if period else "-"
    time_rem = convert_elapsed_to_remaining(box.get('gameTime') or (actions[-1].get('gameTime') if actions else None), period)
    
    date_str = format_date_time(box.get('scheduledTime'))
    v_name = box.get('venue', {}).get('name', '-')
    h_coach = h_data.get("headCoachName") or h_data.get("headCoach", {}).get("lastName", "-")
    g_coach = g_data.get("headCoachName") or g_data.get("headCoach", {}).get("lastName", "-")

    st.markdown(f"""
        <div style='text-align:center;background:#222;color:#fff;padding:15px;border-radius:10px;margin-bottom:20px;'>
            <div style='font-size:0.9em; color:#bbb;'>{date_str} @ {v_name}</div>
            <div style='font-size:1.4em; font-weight:bold;'>{h_name} <span style='font-size:0.6em; color:#aaa;'>(HC: {h_coach})</span></div>
            <div style='font-size:3.5em; font-weight:bold; line-height:1;'>{s_h} : {s_g}</div>
            <div style='font-size:1.4em; font-weight:bold;'>{g_name} <span style='font-size:0.6em; color:#aaa;'>(HC: {g_coach})</span></div>
            <div style='color:#ffcc00; font-weight:bold; font-size:1.4em; margin-top:10px;'>{p_str} | {time_rem}</div>
        </div>
    """, unsafe_allow_html=True)
    
    t1, t2, t3 = st.tabs(["📋 Boxscore", "📊 Team-Vergleich", "📜 Play-by-Play"])
    with t1:
        df_h, df_g = create_live_boxscore_df(h_data), create_live_boxscore_df(g_data)
        def style_row(row):
            if row.get("OnCourt"): return ['background-color: #d4edda; color: #155724'] * len(row)
            return [''] * len(row)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"### {h_name}")
            if not df_h.empty: st.dataframe(df_h.style.apply(style_row, axis=1), hide_index=True, use_container_width=True, height=(len(df_h)+1)*35+3)
        with c2:
            st.markdown(f"### {g_name}")
            if not df_g.empty: st.dataframe(df_g.style.apply(style_row, axis=1), hide_index=True, use_container_width=True, height=(len(df_g)+1)*35+3)
    with t2: render_live_comparison_bars(box)
    with t3: render_full_play_by_play(box)

# --- PREP & SCOUTING ---

def render_prep_dashboard(team_id, team_name, df_roster, last_games, metadata_callback=None):
    st.subheader(f"Analyse: {team_name}")
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown("#### Top 4 Spieler (nach PPG)")
        if df_roster is not None and not df_roster.empty:
            top4 = df_roster.sort_values(by="PPG", ascending=False).head(4)
            for _, row in top4.iterrows():
                with st.container(border=True):
                    col_img, col_stats = st.columns([1, 4])
                    img_url = None
                    if "PLAYER_ID" in row and metadata_callback:
                        img_url = metadata_callback(row["PLAYER_ID"]).get("img")
                    with col_img:
                        if img_url: st.image(img_url, width=80)
                        else: st.markdown("<div style='font-size:30px;'>👤</div>", unsafe_allow_html=True)
                    with col_stats:
                        st.markdown(f"**#{row.get('NR','-')} {row.get('NAME_FULL','Unk')}**")
                        st.markdown(f"**{row.get('PPG',0)} PPG** | FG: {row.get('FG%',0)}% | 3P: {row.get('3PCT',0)}%")
        else: st.warning("Keine Kaderdaten.")
    with c2:
        st.markdown("#### Formkurve")
        if last_games:
            for g in last_games[:5]:
                with st.container(border=True):
                    st.caption(f"{g.get('date','-').split(' ')[0]}")
                    st.write(f"vs {g.get('home') if team_name not in g.get('home') else g.get('guest')}")
                    st.write(f"**{g.get('score')}**")

def analyze_scouting_data(team_id, detailed_games):
    stats = { "games_count": len(detailed_games), "wins": 0, "ato_stats": {"possessions": 0, "points": 0}, "start_stats": {"pts_diff_first_5min": 0}, "top_scorers": {}, "rotation_depth": 0 }
    tid_str = str(team_id)
    for box in detailed_games:
        is_home = box.get('meta_is_home', False)
        s_h = safe_int(box.get("result", {}).get("homeTeamFinalScore") or box.get("homeTeamPoints"))
        s_g = safe_int(box.get("result", {}).get("guestTeamFinalScore") or box.get("guestTeamPoints"))
        if (is_home and s_h > s_g) or (not is_home and s_g > s_h): stats["wins"] += 1
        t_obj = box.get("homeTeam") if is_home else box.get("guestTeam")
        if t_obj:
            active = 0
            for p in t_obj.get("playerStats", []):
                pid = p.get("seasonPlayer", {}).get("id")
                pts, sec = safe_int(p.get("points")), safe_int(p.get("secondsPlayed"))
                if sec > 300: active += 1
                if pid not in stats["top_scorers"]: stats["top_scorers"][pid] = {"name": p.get("seasonPlayer", {}).get("lastName", "Unk"), "pts": 0, "games": 0}
                stats["top_scorers"][pid]["pts"] += pts; stats["top_scorers"][pid]["games"] += 1
            stats["rotation_depth"] += active
        actions = sorted(box.get("actions", []), key=lambda x: x.get('actionNumber', 0))
        sh, sg = 0, 0
        for act in actions:
            if act.get("period") != 1: break
            if act.get("homeTeamPoints") is not None: sh, sg = safe_int(act.get("homeTeamPoints")), safe_int(act.get("guestTeamPoints"))
            if safe_int(act.get("actionNumber")) > 25: break 
        stats["start_stats"]["pts_diff_first_5min"] += (sh - sg if is_home else sg - sh)
        my_sid = str(box.get("homeTeam" if is_home else "guestTeam", {}).get("seasonTeamId"))
        for i, act in enumerate(actions):
            if "TIMEOUT" in str(act.get("type")).upper() and str(act.get("seasonTeamId")) == my_sid:
                stats["ato_stats"]["possessions"] += 1
                for j in range(1, 6):
                    if i+j >= len(actions): break
                    na = actions[i+j]
                    pts, ntid = safe_int(na.get("points")), str(na.get("seasonTeamId"))
                    if pts > 0 and ntid == my_sid: stats["ato_stats"]["points"] += pts; break
                    if (pts > 0 and ntid != my_sid) or (na.get("type") == "TURNOVER" and ntid == my_sid): break
    cnt = stats["games_count"] or 1
    stats["rotation_depth"] = round(stats["rotation_depth"]/cnt, 1)
    stats["start_stats"]["avg_diff"] = round(stats["start_stats"]["pts_diff_first_5min"]/cnt, 1)
    scorer_list = [{"name": d["name"], "ppg": round(d["pts"]/d["games"], 1)} for d in stats["top_scorers"].values() if d["games"] > 0]
    stats["top_scorers_list"] = sorted(scorer_list, key=lambda x: x["ppg"], reverse=True)[:5]
    return stats

def prepare_ai_scouting_context(team_name, detailed_games, team_id):
    ctx = f"Scouting-Daten für Team: {team_name}\nAnzahl Spiele: {len(detailed_games)}\n\n"
    for g in detailed_games:
        is_h = g.get('meta_is_home', False)
        my_sid = str(g.get("homeTeam" if is_h else "guestTeam", {}).get("seasonTeamId"))
        ctx += f"--- Spiel am {g.get('meta_date')} vs {g.get('meta_opponent')} ({g.get('meta_result')}) ---\n"
        p_map = get_player_lookup(g)
        starters = [p_map.get(str(p.get("seasonPlayer", {}).get("id")), "Unbekannt") for p in g.get("homeTeam" if is_h else "guestTeam", {}).get("playerStats", []) if p.get("isStartingFive")]
        ctx += f"Starting 5: {', '.join(starters)}\n"
        actions = sorted(g.get("actions", []), key=lambda x: x.get('actionNumber', 0))
        ctx += "Start Phase Q1:\n"
        for act in actions[:12]:
            tid = str(act.get("seasonTeamId")); actor = "WIR" if tid == my_sid else "GEGNER"
            p_name = p_map.get(str(act.get("seasonPlayerId")), ""); desc = translate_text(act.get("type", ""))
            if act.get("points"): desc += f" (+{act.get('points')} Pkt)"
            ctx += f"- {actor}{' ('+p_name+')' if p_name and actor=='WIR' else ''}: {desc}\n"
        ctx += "ATO (After Timeout):\n"
        for i, act in enumerate(actions):
            if "TIMEOUT" in str(act.get("type")).upper() and str(act.get("seasonTeamId")) == my_sid:
                ctx += "TIMEOUT (WIR). Next Plays:\n"
                for j in range(1, 5):
                    if i+j < len(actions):
                        na = actions[i+j]; who = "WIR" if str(na.get("seasonTeamId")) == my_sid else "GEGNER"
                        p_n = p_map.get(str(na.get("seasonPlayerId")), ""); d = translate_text(na.get("type", ""))
                        if na.get("points"): d += f" (+{na.get('points')} Pkt)"
                        ctx += f"  -> {who}{' ('+p_n+')' if p_n and who=='WIR' else ''}: {d}\n"
        ctx += "\n"
    return ctx

def render_team_analysis_dashboard(team_id, team_name):
    logo = get_best_team_logo(team_id)
    c1, c2 = st.columns([1, 4])
    with c1: 
        if logo: st.image(logo, width=100)
    with c2: st.title(f"Scouting Report: {team_name}")
    with st.spinner("Lade Daten..."):
        games = fetch_last_n_games_complete(team_id, "2025", n=50)
        if not games: st.warning("Keine Spieldaten."); return
        scout = analyze_scouting_data(team_id, games)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Spiele", scout["games_count"], f"{scout['wins']} Siege")
    k2.metric("Start-Qualität", f"{scout['start_stats']['avg_diff']:+.1f}")
    k3.metric("Rotation", scout["rotation_depth"])
    ato_ppp = round(scout["ato_stats"]["points"] / (scout["ato_stats"]["possessions"] or 1), 2)
    k4.metric("ATO Effizienz", f"{ato_ppp} PPP", f"{scout['ato_stats']['possessions']} TOs")
    st.divider()
    col_l, col_r = st.columns([1, 1])
    with col_l:
        st.subheader("🔑 Schlüsselspieler")
        if scout["top_scorers_list"]: st.dataframe(pd.DataFrame(scout["top_scorers_list"]), hide_index=True, use_container_width=True)
        st.markdown("---"); st.subheader("🤖 KI-Prompt")
        ctx = prepare_ai_scouting_context(team_name, games, team_id)
        st.code(f"Du bist ein professioneller Basketball-Scout. Analysiere {team_name}...\n\n{ctx}", language="text")
    with col_r:
        st.subheader("📅 Spiele")
        for g in games:
            with st.expander(f"{g.get('meta_date')} vs {g.get('meta_opponent')} ({g.get('meta_result')})"):
                st.caption(analyze_game_flow(g.get("actions", []), "Heim", "Gast"))

# --- START OF FILE src/analysis_ui.py ---
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import pytz
import openai 
from src.config import SEASON_ID
from src.api import fetch_standings

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
    "unsportsmanlike_foul": "Unsportlich", "half_or_far_distance": "Mitteldistanz", "close_distance": "Nahdistanz"
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
    if isinstance(val, int): return val
    if isinstance(val, float): return int(val)
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

def get_player_team_lookup(box):
    lookup = {}
    h_name = get_team_name(box.get("homeTeam", {}), "Heim")
    g_name = get_team_name(box.get("guestTeam", {}), "Gast")
    for p in box.get("homeTeam", {}).get('playerStats', []):
        pid = str(p.get('seasonPlayer', {}).get('id'))
        lookup[pid] = h_name
    for p in box.get("guestTeam", {}).get('playerStats', []):
        pid = str(p.get('seasonPlayer', {}).get('id'))
        lookup[pid] = g_name
    return lookup

def convert_elapsed_to_remaining(time_str, period):
    if not time_str: return "-"
    base_minutes = 10
    try:
        if int(period) > 4: base_minutes = 5
    except: pass
    
    try:
        parts = time_str.split(":")
        sec = 0
        if len(parts) == 3: sec = int(parts[0])*3600 + int(parts[1])*60 + int(parts[2])
        elif len(parts) == 2: sec = int(parts[0])*60 + int(parts[1])
        else: return time_str
        
        rem = (base_minutes * 60) - sec
        if rem < 0: rem = 0
        return f"{rem // 60:02d}:{rem % 60:02d}"
    except: return time_str

def calculate_advanced_stats_from_actions(actions, home_id, guest_id):
    stats = {"h_lead": 0, "g_lead": 0, "h_run": 0, "g_run": 0, "h_paint": 0, "g_paint": 0, "h_2nd": 0, "g_2nd": 0, "h_fb": 0, "g_fb": 0}
    if not actions: return stats
    cur_h = 0; cur_g = 0; run_team = None; run_score = 0; hid_str = str(home_id)
    for act in actions:
         new_h = safe_int(act.get("homeTeamPoints")); new_g = safe_int(act.get("guestTeamPoints"))
         if new_h == 0 and new_g == 0 and act.get("homeTeamPoints") is None: new_h = cur_h; new_g = cur_g
         pts_h = new_h - cur_h; pts_g = new_g - cur_g
         if pts_h > 0:
             if run_team == "home": run_score += pts_h
             else: run_team = "home"; run_score = pts_h
             if run_score > stats["h_run"]: stats["h_run"] = run_score
         elif pts_g > 0:
             if run_team == "guest": run_score += pts_g
             else: run_team = "guest"; run_score = pts_g
             if run_score > stats["g_run"]: stats["g_run"] = run_score
         pts_total = pts_h + pts_g
         if pts_total > 0:
             act_tid = str(act.get("seasonTeamId", ""))
             is_home_action = (act_tid == hid_str) if act_tid else (pts_h > 0)
             qualifiers = act.get("qualifiers", []); q_str = " ".join([str(x).lower() for x in qualifiers]); type_str = str(act.get("type", "")).lower()
             if "fastbreak" in q_str or "fastbreak" in type_str:
                 if is_home_action: stats["h_fb"] += pts_total
                 else: stats["g_fb"] += pts_total
             if "paint" in q_str or "inside" in q_str or "layup" in type_str:
                 if is_home_action: stats["h_paint"] += pts_total
                 else: stats["g_paint"] += pts_total
             if "second" in q_str or "2nd" in q_str:
                 if is_home_action: stats["h_2nd"] += pts_total
                 else: stats["g_2nd"] += pts_total
         diff = new_h - new_g
         if diff > 0 and diff > stats["h_lead"]: stats["h_lead"] = diff
         if diff < 0 and abs(diff) > stats["g_lead"]: stats["g_lead"] = abs(diff)
         cur_h = new_h; cur_g = new_g
    return stats

def analyze_game_flow(actions, home_name, guest_name):
    if not actions: return "Keine Play-by-Play Daten verfügbar."
    lead_changes = 0; ties = 0; last_leader = None; crunch_log = []
    for act in actions:
        h_score = safe_int(act.get("homeTeamPoints")); g_score = safe_int(act.get("guestTeamPoints"))
        if h_score == 0 and g_score == 0: continue
        if h_score > g_score: current_leader = 'home'
        elif g_score > h_score: current_leader = 'guest'
        else: current_leader = 'tie'
        if last_leader is not None:
            if current_leader != last_leader:
                if current_leader == 'tie': ties += 1
                elif last_leader != 'tie': lead_changes += 1
                elif last_leader == 'tie': lead_changes += 1
        last_leader = current_leader

    relevant_types = ["TWO_POINT_SHOT_MADE", "THREE_POINT_SHOT_MADE", "FREE_THROW_MADE", "TURNOVER", "FOUL", "TIMEOUT"]
    filtered_actions = [a for a in actions if a.get("type") in relevant_types]
    last_events = filtered_actions[-12:] 
    crunch_log.append("\n**Die Schlussphase (Chronologie der letzten Ereignisse):**")
    for ev in last_events:
        h_pts = ev.get('homeTeamPoints'); g_pts = ev.get('guestTeamPoints'); score_str = f"{h_pts}:{g_pts}"
        action_desc = translate_text(ev.get("type", ""))
        if ev.get("points"): action_desc += f" (+{ev.get('points')})"
        crunch_log.append(f"- {score_str}: {action_desc}")

    summary = f"Führungswechsel: {lead_changes}, Unentschieden: {ties}.\n"
    summary += "\n".join(crunch_log)
    return summary

# --- RENDERING FUNKTIONEN ---

def render_full_play_by_play(box, height=600):
    actions = box.get("actions", [])
    if not actions:
        st.info("Keine Play-by-Play Daten verfügbar.")
        return
    player_map = get_player_lookup(box)
    player_team_map = get_player_team_lookup(box)
    home_name = get_team_name(box.get("homeTeam", {}), "Heim")
    guest_name = get_team_name(box.get("guestTeam", {}), "Gast")
    home_id = str(box.get("homeTeam", {}).get("seasonTeamId", "HOME"))
    guest_id = str(box.get("guestTeam", {}).get("seasonTeamId", "GUEST"))
    data = []
    running_h, running_g = 0, 0
    for act in actions:
        h_pts = act.get("homeTeamPoints")
        g_pts = act.get("guestTeamPoints")
        if h_pts is not None: running_h = safe_int(h_pts)
        if g_pts is not None: running_g = safe_int(g_pts)
        score_str = f"{running_h} : {running_g}"
        period = act.get("period", "")
        game_time = act.get("gameTime", "") 
        if game_time:
            display_time = convert_elapsed_to_remaining(game_time, period)
        else:
            display_time = "-"
        time_label = f"Q{period} {display_time}" if period else "-"
        pid = str(act.get("seasonPlayerId"))
        actor = player_map.get(pid, "")
        tid = str(act.get("seasonTeamId"))
        if tid == home_id: team_display = home_name
        elif tid == guest_id: team_display = guest_name
        elif pid in player_team_map: team_display = player_team_map[pid]
        else: team_display = "-" 
        raw_type = act.get("type", "")
        action_german = translate_text(raw_type)
        if "Wurf" in action_german or "Freiwurf" in action_german:
             if act.get("isSuccessful") is True: action_german += " (Treffer)"
             elif act.get("isSuccessful") is False: action_german += " (Fehlwurf)"
        qualifiers = act.get("qualifiers", [])
        if qualifiers:
            qual_german = [translate_text(q) for q in qualifiers]
            action_german += f" ({', '.join(qual_german)})"
        if act.get("points"): action_german += f" (+{act.get('points')})"
        data.append({"Zeit": time_label, "Score": score_str, "Team": team_display, "Spieler": actor, "Aktion": action_german})
    df = pd.DataFrame(data)
    if not df.empty: df = df.iloc[::-1]
    st.dataframe(df, use_container_width=True, hide_index=True, height=height)

def render_game_header(details):
    h_data = details.get("homeTeam", {}); g_data = details.get("guestTeam", {})
    h_name = get_team_name(h_data, "Heim"); g_name = get_team_name(g_data, "Gast")
    res = details.get("result", {}); score_h = res.get("homeTeamFinalScore", 0); score_g = res.get("guestTeamFinalScore", 0)
    time_str = format_date_time(details.get("scheduledTime"))
    venue_str = "-"
    if details.get("venue"):
        venue = details["venue"]
        venue_str = f"{venue.get('name', '-')}, {venue.get('address', '').split(',')[-1].strip()}"
    refs = [f"{r.get('lastName', '')} {r.get('firstName', '')}".strip() for i in range(1, 4) if (r := details.get(f"referee{i}")) and isinstance(r, dict)]
    ref_str = ", ".join(refs) if refs else "-"
    st.markdown(f"<div style='text-align: center; color: #666; font-size: 1.1em;'>📍 {venue_str} | 🕒 {time_str}</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([2, 1, 2])
    with c1: st.markdown(f"## {h_name}")
    with c2:
        st.markdown(f"<h1 style='text-align: center;'>{score_h} : {score_g}</h1>", unsafe_allow_html=True)
        q_data = {f"Q{i}": [res.get(f"homeTeamQ{i}Score",0), res.get(f"guestTeamQ{i}Score",0)] for i in range(1, 5)}
        if res.get("homeTeamOT1Score", 0) > 0: q_data["OT"] = [res.get("homeTeamOT1Score",0), res.get("guestTeamOT1Score",0)]
        q_html = "<table style='width:100%; font-size:12px; border-collapse:collapse; margin:0 auto; text-align:center;'><tr style='border-bottom:1px solid #ddd;'><th></th>" + "".join([f"<th>{k}</th>" for k in q_data.keys()]) + "</tr>"
        q_html += f"<tr><td style='font-weight:bold;'>{h_name[:3].upper()}</td>" + "".join([f"<td>{v[0]}</td>" for v in q_data.values()]) + "</tr>"
        q_html += f"<tr><td style='font-weight:bold;'>{g_name[:3].upper()}</td>" + "".join([f"<td>{v[1]}</td>" for v in q_data.values()]) + "</tr></table>"
        st.markdown(q_html, unsafe_allow_html=True)
    with c3: st.markdown(f"## {g_name}")
    st.write("---")
    st.markdown(f"<div style='display: flex; justify-content: space-between; font-size: 14px; background-color: #f9f9f9; padding: 10px; border-radius: 5px;'><span>👥 <b>Zuschauer:</b> {res.get('spectators', '-')}</span><span>⚖️ <b>Refs:</b> {ref_str}</span><span>🆔 <b>ID:</b> {details.get('id', '-')}</span></div>", unsafe_allow_html=True)

def render_boxscore_table_pro(player_stats, team_stats_official, team_name, coach_name="-"):
    if not player_stats: return
    data = []
    for p in player_stats:
        info = p.get("seasonPlayer", {}); name = f"{info.get('lastName', '')}, {info.get('firstName', '')}"; nr = info.get("shirtNumber", "-"); starter = "*" if p.get("isStartingFive") else ""; sec = safe_int(p.get("secondsPlayed"))
        pts = safe_int(p.get("points")); m2 = safe_int(p.get("twoPointShotsMade")); a2 = safe_int(p.get("twoPointShotsAttempted")); p2 = safe_int(p.get("twoPointShotSuccessPercent"))
        m3 = safe_int(p.get("threePointShotsMade")); a3 = safe_int(p.get("threePointShotsAttempted")); p3 = safe_int(p.get("threePointShotSuccessPercent"))
        mfg = safe_int(p.get("fieldGoalsMade")); afg = safe_int(p.get("fieldGoalsAttempted")); pfg = safe_int(p.get("fieldGoalsSuccessPercent"))
        mft = safe_int(p.get("freeThrowsMade")); aft = safe_int(p.get("freeThrowsAttempted")); pft = safe_int(p.get("freeThrowsSuccessPercent"))
        oreb = safe_int(p.get("offensiveRebounds")); dreb = safe_int(p.get("defensiveRebounds")); treb = safe_int(p.get("totalRebounds"))
        ast = safe_int(p.get("assists")); stl = safe_int(p.get("steals")); tov = safe_int(p.get("turnovers")); blk = safe_int(p.get("blocks")); pf = safe_int(p.get("foulsCommitted")); eff = safe_int(p.get("efficiency")); pm = safe_int(p.get("plusMinus"))
        min_str = f"{int(sec//60):02d}:{int(sec%60):02d}" if sec > 0 else "DNP"
        s_2p = f"{m2}/{a2} ({int(p2)}%)" if a2 and sec > 0 else ""; s_3p = f"{m3}/{a3} ({int(p3)}%)" if a3 and sec > 0 else ""; s_fg = f"{mfg}/{afg} ({int(pfg)}%)" if sec > 0 else ""; s_ft = f"{mft}/{aft} ({int(pft)}%)" if aft and sec > 0 else ""
        data.append({"No.": f"{starter}{nr}", "Name": name, "Min": min_str, "PTS": pts, "2P": s_2p, "3P": s_3p, "FG": s_fg, "FT": s_ft, "OR": oreb, "DR": dreb, "TR": treb, "AS": ast, "ST": stl, "TO": tov, "BS": blk, "PF": pf, "EFF": eff, "+/-": pm})
    
    # Rest der Funktion für Team/Totals...
    df = pd.DataFrame(data)
    st.markdown(f"#### {team_name}"); calc_height = (len(df) + 1) * 35 + 3
    st.dataframe(df, hide_index=True, use_container_width=True, height=calc_height)
    if coach_name and coach_name != "-": st.markdown(f"*Head Coach: {coach_name}*")

def render_game_top_performers(box):
    h_data = box.get("homeTeam", {}); g_data = box.get("guestTeam", {}); h_name = get_team_name(h_data, "Heim"); g_name = get_team_name(g_data, "Gast")
    def get_top3(stats_list, key="points"):
        active = [p for p in stats_list if safe_int(p.get("secondsPlayed")) > 0]
        return sorted(active, key=lambda x: safe_int(x.get(key)), reverse=True)[:3]
    def mk_box(players, title, color, val_key="points"):
        html = f"<div style='flex:1; border:1px solid #ccc; margin:5px;'><div style='background:{color}; color:white; padding:5px; font-weight:bold; text-align:center;'>{title}</div><table style='width:100%; border-collapse:collapse;'>"
        for p in players:
             name = f"{p.get('seasonPlayer', {}).get('lastName', '')}"; val = safe_int(p.get(val_key))
             html += f"<tr><td style='padding:6px; font-size:16px;'>{name}</td><td style='padding:6px; text-align:right; font-weight:bold; font-size:16px;'>{val}</td></tr>"
        return html + "</table></div>"
    st.markdown("#### Top Performer")
    html = f"""<div style="display:flex; flex-direction:row; gap:10px; margin-bottom:20px;">{mk_box(get_top3(h_data.get("playerStats", []), "points"), f"Points ({h_name})", "#e35b00", "points")}{mk_box(get_top3(g_data.get("playerStats", []), "points"), f"Points ({g_name})", "#e35b00", "points")}</div><div style="display:flex; flex-direction:row; gap:10px; margin-bottom:20px;">{mk_box(get_top3(h_data.get("playerStats", []), "totalRebounds"), f"Rebounds ({h_name})", "#0055ff", "totalRebounds")}{mk_box(get_top3(g_data.get("playerStats", []), "totalRebounds"), f"Rebounds ({g_name})", "#0055ff", "totalRebounds")}</div>"""
    st.markdown(html, unsafe_allow_html=True)

def render_charts_and_stats(box):
    h = box.get("homeTeam", {}).get("gameStat", {}); g = box.get("guestTeam", {}).get("gameStat", {}); h_name = get_team_name(box.get("homeTeam", {}), "Heim"); g_name = get_team_name(box.get("guestTeam", {}), "Gast"); actions = box.get("actions", []); hid = str(box.get("homeTeam", {}).get("seasonTeam", {}).get("seasonTeamId", "0")); gid = str(box.get("guestTeam", {}).get("seasonTeam", {}).get("seasonTeamId", "0")); cs = calculate_advanced_stats_from_actions(actions, hid, gid)
    def mk_label(pct, made, att): return f"{pct}% ({made}/{att})"
    categories = ["Field Goals", "2 Points", "3 Points", "Free Throws"]
    h_vals = [{"Team": h_name, "Cat": "Field Goals", "Pct": safe_int(h.get('fieldGoalsSuccessPercent')), "Label": mk_label(safe_int(h.get('fieldGoalsSuccessPercent')), safe_int(h.get('fieldGoalsMade')), safe_int(h.get('fieldGoalsAttempted')))}, {"Team": h_name, "Cat": "2 Points", "Pct": safe_int(h.get('twoPointShotSuccessPercent')), "Label": mk_label(safe_int(h.get('twoPointShotSuccessPercent')), safe_int(h.get('twoPointShotsMade')), safe_int(h.get('twoPointShotsAttempted')))}, {"Team": h_name, "Cat": "3 Points", "Pct": safe_int(h.get('threePointShotSuccessPercent')), "Label": mk_label(safe_int(h.get('threePointShotSuccessPercent')), safe_int(h.get('threePointShotsMade')), safe_int(h.get('threePointShotsAttempted')))}, {"Team": h_name, "Cat": "Free Throws", "Pct": safe_int(h.get('freeThrowsSuccessPercent')), "Label": mk_label(safe_int(h.get('freeThrowsSuccessPercent')), safe_int(h.get('freeThrowsMade')), safe_int(h.get('freeThrowsAttempted')))}]
    g_vals = [{"Team": g_name, "Cat": "Field Goals", "Pct": safe_int(g.get('fieldGoalsSuccessPercent')), "Label": mk_label(safe_int(g.get('fieldGoalsSuccessPercent')), safe_int(g.get('fieldGoalsMade')), safe_int(g.get('fieldGoalsAttempted')))}, {"Team": g_name, "Cat": "2 Points", "Pct": safe_int(g.get('twoPointShotSuccessPercent')), "Label": mk_label(safe_int(g.get('twoPointShotSuccessPercent')), safe_int(g.get('twoPointShotsMade')), safe_int(g.get('twoPointShotsAttempted')))}, {"Team": g_name, "Cat": "3 Points", "Pct": safe_int(g.get('threePointShotSuccessPercent')), "Label": mk_label(safe_int(g.get('threePointShotSuccessPercent')), safe_int(g.get('threePointShotsMade')), safe_int(g.get('threePointShotsAttempted')))}, {"Team": g_name, "Cat": "Free Throws", "Pct": safe_int(g.get('freeThrowsSuccessPercent')), "Label": mk_label(safe_int(g.get('freeThrowsSuccessPercent')), safe_int(g.get('freeThrowsMade')), safe_int(g.get('freeThrowsAttempted')))}]
    source = pd.DataFrame(h_vals + g_vals)
    chart = (alt.Chart(source).encode(x=alt.X('Cat', sort=categories, title=None), xOffset='Team', y=alt.Y('Pct', title=None, axis=None)).mark_bar().encode(color=alt.Color('Team', legend=alt.Legend(title=None, orient='top')), tooltip=['Team', 'Cat', 'Label']) + alt.Chart(source).encode(x=alt.X('Cat', sort=categories), xOffset='Team', y=alt.Y('Pct')).mark_text(dy=-10, color='black').encode(text='Label')).properties(height=350)
    metrics = [("Offensive Rebounds", safe_int(h.get('offensiveRebounds')), safe_int(g.get('offensiveRebounds'))), ("Defensive Rebounds", safe_int(h.get('defensiveRebounds')), safe_int(g.get('defensiveRebounds'))), ("Total Rebounds", safe_int(h.get('totalRebounds')), safe_int(g.get('totalRebounds'))), ("Assists", safe_int(h.get("assists")), safe_int(g.get("assists"))), ("Fouls", safe_int(h.get("foulsCommitted")), safe_int(g.get("foulsCommitted"))), ("Turnovers", safe_int(h.get("turnovers")), safe_int(g.get("turnovers"))), ("Steals", safe_int(h.get("steals")), safe_int(g.get("steals"))), ("Blocks", safe_int(h.get("blocks")), safe_int(g.get("blocks"))), ("Points in Paint", cs["h_paint"], cs["g_paint"]), ("2nd Chance Pts", cs["h_2nd"], cs["g_2nd"]), ("Fastbreak Pts", cs["h_fb"], cs["g_fb"]), ("Biggest Lead", cs.get("h_lead", "-"), cs.get("g_lead", "-")), ("Biggest Run", cs.get("h_run", "-"), cs.get("g_run", "-"))]
    c1, c2 = st.columns([1, 1]); 
    with c1: st.markdown("#### Wurfquoten"); st.altair_chart(chart, use_container_width=True)
    with c2: 
        st.markdown("#### Team Statistik"); html = f"<table style='width:100%; border-collapse: collapse; font-family: sans-serif; font-size: 14px;'><tr style='background-color:#003366; color:white;'><th style='padding:8px; text-align:center; width:30%;'>{h_name}</th><th style='padding:8px; text-align:center; width:40%;'>Kategorie</th><th style='padding:8px; text-align:center; width:30%;'>{g_name}</th></tr>"
        for label, vh, vg in metrics: html += f"<tr style='border-bottom:1px solid #eee;'><td style='padding:6px; text-align:center;'>{vh}</td><td style='padding:6px; text-align:center; font-weight:bold; color:#555;'>{label}</td><td style='padding:6px; text-align:center;'>{vg}</td></tr>"
        st.markdown(html + "</table>", unsafe_allow_html=True)

def generate_game_summary(box):
    if not box: return "Keine Daten verfügbar."
    h_data = box.get("homeTeam", {}); g_data = box.get("guestTeam", {}); h_name = get_team_name(h_data, "Heim"); g_name = get_team_name(g_data, "Gast"); res = box.get("result", {}); s_h = res.get("homeTeamFinalScore", 0); s_g = res.get("guestTeamFinalScore", 0); winner = h_name if s_h > s_g else g_name; diff = abs(s_h - s_g)
    text = f"**Endergebnis:** {h_name} {s_h} : {s_g} {g_name}\n\n"; 
    if diff < 6: text += f"In einem bis zur letzten Sekunde spannenden Krimi setzte sich {winner} knapp durch. "
    elif diff > 20: text += f"{winner} dominierte das Spiel deutlich und gewann souverän mit {diff} Punkten Vorsprung. "
    else: text += f"{winner} konnte das Spiel mit einem soliden {diff}-Punkte-Vorsprung für sich entscheiden. "
    def get_best(p_list, key):
        if not p_list: return None, 0
        s = sorted(p_list, key=lambda x: safe_int(x.get(key)), reverse=True)
        if not s: return "N/A", 0
        p = s[0]; return p.get("seasonPlayer", {}).get("lastName", "Unknown"), safe_int(p.get(key))
    h_p, h_v = get_best(h_data.get("playerStats", []), "points"); g_p, g_v = get_best(g_data.get("playerStats", []), "points")
    text += f"\n\n**Top Performer:**\nAuf Seiten von {h_name} war **{h_p}** mit {h_v} Punkten am erfolgreichsten. Bei {g_name} hielt **{g_p}** mit {g_v} Zählern dagegen."
    return text

def generate_complex_ai_prompt(box):
    if not box: return "Keine Daten."
    h_data = box.get("homeTeam", {}); g_data = box.get("guestTeam", {}); h_name = get_team_name(h_data, "Heim"); g_name = get_team_name(g_data, "Gast"); res = box.get("result", {}); pbp_summary = analyze_game_flow(box.get("actions", []), h_name, g_name)
    def get_stats_str(team_data):
        s = team_data.get("gameStat", {}); p_list = team_data.get("playerStats", []); top_p = sorted([p for p in p_list if p.get("points", 0) is not None], key=lambda x: x.get("points", 0), reverse=True)[:2]; top_str = ", ".join([f"{p.get('seasonPlayer', {}).get('lastName')} ({p.get('points')} Pkt)" for p in top_p])
        return f"FG: {safe_int(s.get('fieldGoalsSuccessPercent'))}%, Reb: {safe_int(s.get('totalRebounds'))}, TO: {safe_int(s.get('turnovers'))}, Top: {top_str}"
    prompt = f"""Erstelle 3 journalistische Spielberichte (Heim-Sicht, Neutral, Gäste-Sicht) basierend auf diesen Daten:\nHeim: {h_name}, Gast: {g_name}, Ergebnis: {res.get('homeTeamFinalScore')} : {res.get('guestTeamFinalScore')}\nStats Heim: {get_stats_str(h_data)}\nStats Gast: {get_stats_str(g_data)}\n\nSPIELVERLAUF:\n{pbp_summary}\n\nANWEISUNGEN:\nSchreibe lebendig, emotional und detailreich."""
    return prompt

def run_openai_generation(api_key, prompt):
    client = openai.OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": "Du bist ein Sportjournalist."}, {"role": "user", "content": prompt}], temperature=0.7)
        return response.choices[0].message.content
    except Exception as e: return f"Fehler: {str(e)}"

def render_prep_dashboard(team_id, team_name, df_roster, last_games, metadata_callback=None, staffel="Süd"):
    st.subheader(f"Analyse: {team_name}")
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.markdown("#### Top 4 Spieler (nach PPG)")
        if df_roster is not None and not df_roster.empty:
            top4 = df_roster.sort_values(by="PPG", ascending=False).head(4)
            for _, row in top4.iterrows():
                with st.container():
                    col_img, col_stats = st.columns([1, 4])
                    age, nat, height = row.get('AGE', '-'), row.get('NATIONALITY', '-'), row.get('HEIGHT_ROSTER', '-')
                    img_url = None
                    if metadata_callback:
                        meta = None
                        if age in ["-", ""] or nat in ["-", ""] or height in ["-", ""] or not row.get("img"):
                            meta = metadata_callback(row["PLAYER_ID"])
                        if meta:
                            if age in ["-", ""]: age = meta.get("age", "-")
                            if nat in ["-", ""]: nat = meta.get("nationality", "-")
                            if height in ["-", ""]: height = meta.get("height", "-")
                            img_url = meta.get("img")
                        else: img_url = row.get("img")
                    else: img_url = row.get("img")
                    with col_img:
                        if img_url: st.image(img_url, width=100)
                        else: st.markdown("<div style='font-size:30px; text-align:center;'>👤</div>", unsafe_allow_html=True)
                    with col_stats:
                        st.markdown(f"**#{row['NR']} {row['NAME_FULL']}**")
                        st.caption(f"Alter: {age} | Nat: {nat} | Größe: {height}")
                        st.markdown(f"**PPG: {row['PPG']}** | FG%: {row['FG%']} | 3P%: {row['3PCT']}% | REB: {row['TOT']} | AST: {row['AS']}")
                    st.divider()
        else: st.warning("Keine Kaderdaten.")

    with c2:
        st.markdown("#### Formkurve")
        if last_games:
            played_games = [g for g in last_games if g.get('has_result')]
            def parse_date(d_str):
                try: return datetime.strptime(d_str, "%d.%m.%Y %H:%M")
                except: return datetime.min
            games_sorted = sorted(played_games, key=lambda x: parse_date(x['date']), reverse=True)[:5]
            if games_sorted:
                st.write("") 
                cols_form = st.columns(len(games_sorted))
                for idx, g in enumerate(games_sorted):
                    is_home = (g.get('homeTeamId') == str(team_id))
                    win = (is_home and g.get('home_score', 0) > g.get('guest_score', 0)) or \
                          (not is_home and g.get('guest_score', 0) > g.get('home_score', 0))
                    color, char = ("#28a745", "W") if win else ("#dc3545", "L")
                    with cols_form[idx]:
                        st.markdown(f"<div style='background-color:{color};color:white;text-align:center;padding:10px;border-radius:5px;font-weight:bold;' title='{g['date']}\n{g['home']} vs {g['guest']}\n{g['score']}'>{char}</div>", unsafe_allow_html=True)
            else: st.info("Keine gespielten Spiele.")
        else: st.info("Keine Spiele.")
        
        st.write("")
        st.markdown("#### Aktueller Tabellenplatz")
        standings_map = fetch_standings(SEASON_ID, staffel)
        if standings_map:
            team_stat = standings_map.get(str(team_id))
            if team_stat:
                rank, team_n, played = team_stat.get("rank", "-"), team_stat.get("team", {}).get("name", team_name), team_stat.get("matchesPlayed", 0)
                wins, losses, pts = team_stat.get("wins", 0), team_stat.get("losses", 0), team_stat.get("points", 0)
                diff, streak = team_stat.get("pointsDifference", 0), team_stat.get("streak", "-")
                html_table = f"""<table style="width:100%; font-size:12px; border-collapse: collapse; text-align: center;"><tr style="background-color: #f0f0f0; border-bottom: 1px solid #ddd;"><th style="padding: 4px;">PL</th><th style="padding: 4px; text-align: left;">Team</th><th>G</th><th>S</th><th>N</th><th>PKT</th><th>Diff</th><th>Serie</th></tr><tr style="border-bottom: 1px solid #eee;"><td style="font-weight: bold;">{rank}</td><td style="text-align: left;">{team_n}</td><td>{played}</td><td style="color: green;">{wins}</td><td style="color: red;">{losses}</td><td style="font-weight: bold;">{pts}</td><td>{diff}</td><td>{streak}</td></tr></table>"""
                st.markdown(html_table, unsafe_allow_html=True)
            else:
                 st.warning(f"Team (ID: {team_id}) nicht in den Tabellendaten für Staffel '{staffel}' (Saison {SEASON_ID}) gefunden.")
        else:
            st.warning(f"Tabellendaten für Staffel '{staffel}' (Saison {SEASON_ID}) konnten nicht geladen werden. Bitte prüfen Sie die `SEASON_ID` und die Netzwerkverbindung.")

def render_live_view(box):
    if not box: return
    h_name, g_name = get_team_name(box.get("homeTeam", {}), "Heim"), get_team_name(box.get("guestTeam", {}), "Gast")
    res = box.get("result", {}); s_h, s_g = res.get("homeTeamFinalScore", 0), res.get("guestTeamFinalScore", 0)
    actions = box.get("actions", []); period = res.get("period") or box.get("period", 1)
    found_score = False
    if actions:
        for act in reversed(actions):
            if act.get("homeTeamPoints") is not None and act.get("guestTeamPoints") is not None:
                s_h, s_g = safe_int(act.get("homeTeamPoints")), safe_int(act.get("guestTeamPoints"))
                if not period: period = act.get("period")
                found_score = True
                break
    p_map = {1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"}
    p_str = f"OT{safe_int(period)-4}" if safe_int(period) > 4 else p_map.get(safe_int(period), f"Q{period}") if period else "-"
    time_str = convert_elapsed_to_remaining(box.get('gameTime', ''), period)
    st.markdown(f"<div style='text-align: center; background-color: #222; color: #fff; padding: 10px; border-radius: 10px; margin-bottom: 20px;'><div style='font-size: 1.2em;'>{h_name} vs {g_name}</div><div style='font-size: 3em; font-weight: bold;'>{s_h} : {s_g}</div><div style='font-size: 0.9em; color: #ccc;'>{p_str} | {time_str}</div></div>", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("📊 Live Stats")
        def create_live_player_table(team_data):
            players = team_data.get("playerStats", [])
            data = [
                {"Nr": p.get('seasonPlayer', {}).get('shirtNumber', '-'), "Name": p.get('seasonPlayer', {}).get('lastName', 'Unk'), "Min": f"{int((sec:=safe_int(p.get('secondsPlayed')))//60):02d}:{int(sec%60):02d}", "PTS": safe_int(p.get("points")), "PF": safe_int(p.get("foulsCommitted"))}
                for p in players if safe_int(p.get("secondsPlayed")) > 0 or safe_int(p.get("points")) > 0
            ]
            df = pd.DataFrame(data)
            return df.sort_values(by="PTS", ascending=False) if not df.empty else df
        df_home, df_guest = create_live_player_table(box.get("homeTeam", {})), create_live_player_table(box.get("guestTeam", {}))
        st.markdown(f"**{h_name}**"); st.dataframe(df_home, hide_index=True, use_container_width=True)
        st.write(""); st.markdown(f"**{g_name}**"); st.dataframe(df_guest, hide_index=True, use_container_width=True)
    with c2:
        st.subheader("📜 Live Ticker")
        render_full_play_by_play(box, height=800)

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
    data = []; running_h = 0; running_g = 0
    
    actions_sorted = sorted(actions, key=lambda x: x.get('actionNumber', 0))

    for act in actions_sorted:
        h_pts = act.get("homeTeamPoints"); g_pts = act.get("guestTeamPoints")
        if h_pts is not None: running_h = safe_int(h_pts)
        if g_pts is not None: running_g = safe_int(g_pts)
        score_str = f"{running_h} : {running_g}"
        period = act.get("period", ""); game_time = act.get("gameTime", ""); time_in_game = act.get("timeInGame", "") 
        if game_time: display_time = convert_elapsed_to_remaining(game_time, period)
        else:
            display_time = "-"
            if time_in_game and "M" in time_in_game:
                try: t = time_in_game.replace("PT", "").replace("S", ""); m, s = t.split("M"); display_time = f"{m}:{s.zfill(2)}"
                except: pass
        time_label = f"Q{period} {display_time}" if period else "-"
        pid = str(act.get("seasonPlayerId")); actor = player_map.get(pid, "")
        tid = str(act.get("seasonTeamId"))
        if tid == home_id: team_display = home_name
        elif tid == guest_id: team_display = guest_name
        elif pid in player_team_map: team_display = player_team_map[pid]
        else: team_display = "-" 
        raw_type = act.get("type", ""); action_german = translate_text(raw_type)
        is_successful = act.get("isSuccessful")
        if "Wurf" in action_german or "Freiwurf" in action_german or "Treffer" in action_german or "Fehlwurf" in action_german:
             if "Treffer" not in action_german and "Fehlwurf" not in action_german:
                 if is_successful is True: action_german += " (Treffer)"
                 elif is_successful is False: action_german += " (Fehlwurf)"
        qualifiers = act.get("qualifiers", [])
        if qualifiers: qual_german = [translate_text(q) for q in qualifiers]; action_german += f" ({', '.join(qual_german)})"
        if act.get("points"): action_german += f" (+{act.get('points')})"
        data.append({"Zeit": time_label, "Score": score_str, "Team": team_display, "Spieler": actor, "Aktion": action_german})
    
    df = pd.DataFrame(data)
    
    # Umdrehen damit aktuellstes oben
    if not df.empty:
        df = df.iloc[::-1]
        
    st.dataframe(df, use_container_width=True, hide_index=True, height=height)

def render_game_header(details):
    h_data = details.get("homeTeam", {}); g_data = details.get("guestTeam", {})
    h_name = get_team_name(h_data, "Heim"); g_name = get_team_name(g_data, "Gast")
    res = details.get("result", {}); score_h = res.get("homeTeamFinalScore", 0); score_g = res.get("guestTeamFinalScore", 0)
    time_str = format_date_time(details.get("scheduledTime"))
    venue = details.get("venue", {}); venue_str = f"{venue.get('name', '-')}, {venue.get('address', '').split(',')[-1].strip()}"
    refs = []
    for i in range(1, 4):
        r = details.get(f"referee{i}")
        if r and isinstance(r, dict): fn = r.get("firstName", ""); ln = r.get("lastName", ""); refs.append(f"{ln} {fn}".strip())
    ref_str = ", ".join(refs) if refs else "-"
    st.markdown(f"<div style='text-align: center; color: #666; font-size: 1.1em;'>📍 {venue_str} | 🕒 {time_str}</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([2, 1, 2])
    with c1: st.markdown(f"## {h_name}")
    with c2:
        st.markdown(f"<h1 style='text-align: center;'>{score_h} : {score_g}</h1>", unsafe_allow_html=True)
        q_data = { "Q1": [res.get("homeTeamQ1Score",0), res.get("guestTeamQ1Score",0)], "Q2": [res.get("homeTeamQ2Score",0), res.get("guestTeamQ2Score",0)], "Q3": [res.get("homeTeamQ3Score",0), res.get("guestTeamQ3Score",0)], "Q4": [res.get("homeTeamQ4Score",0), res.get("guestTeamQ4Score",0)] }
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
    data = []; sum_pts=0; sum_3pm=0; sum_3pa=0; sum_fgm=0; sum_fga=0; sum_ftm=0; sum_fta=0; sum_or=0; sum_dr=0; sum_tr=0; sum_as=0; sum_st=0; sum_to=0; sum_bs=0; sum_pf=0; sum_eff=0; sum_pm=0
    for p in player_stats:
        info = p.get("seasonPlayer", {}); name = f"{info.get('lastName', '')}, {info.get('firstName', '')}"; nr = info.get("shirtNumber", "-"); starter = "*" if p.get("isStartingFive") else ""; sec = safe_int(p.get("secondsPlayed"))
        pts = safe_int(p.get("points")); sum_pts += pts; m2 = safe_int(p.get("twoPointShotsMade")); a2 = safe_int(p.get("twoPointShotsAttempted")); p2 = safe_int(p.get("twoPointShotSuccessPercent"))
        m3 = safe_int(p.get("threePointShotsMade")); a3 = safe_int(p.get("threePointShotsAttempted")); p3 = safe_int(p.get("threePointShotSuccessPercent")); sum_3pm += m3; sum_3pa += a3
        mfg = safe_int(p.get("fieldGoalsMade")); afg = safe_int(p.get("fieldGoalsAttempted")); pfg = safe_int(p.get("fieldGoalsSuccessPercent")); sum_fgm += mfg; sum_fga += afg
        mft = safe_int(p.get("freeThrowsMade")); aft = safe_int(p.get("freeThrowsAttempted")); pft = safe_int(p.get("freeThrowsSuccessPercent")); sum_ftm += mft; sum_fta += aft
        oreb = safe_int(p.get("offensiveRebounds")); sum_or += oreb; dreb = safe_int(p.get("defensiveRebounds")); sum_dr += dreb; treb = safe_int(p.get("totalRebounds")); sum_tr += treb
        ast = safe_int(p.get("assists")); sum_as += ast; stl = safe_int(p.get("steals")); sum_st += stl; tov = safe_int(p.get("turnovers")); sum_to += tov; blk = safe_int(p.get("blocks")); sum_bs += blk; pf = safe_int(p.get("foulsCommitted")); sum_pf += pf; eff = safe_int(p.get("efficiency")); sum_eff += eff; pm = safe_int(p.get("plusMinus")); sum_pm += pm
        min_str = f"{int(sec//60):02d}:{int(sec%60):02d}" if sec > 0 else "DNP"
        s_2p = f"{m2}/{a2} ({int(p2)}%)" if a2 and sec > 0 else ""; s_3p = f"{m3}/{a3} ({int(p3)}%)" if a3 and sec > 0 else ""; s_fg = f"{mfg}/{afg} ({int(pfg)}%)" if sec > 0 else ""; s_ft = f"{mft}/{aft} ({int(pft)}%)" if aft and sec > 0 else ""
        data.append({"No.": f"{starter}{nr}", "Name": name, "Min": min_str, "PTS": pts, "2P": s_2p, "3P": s_3p, "FG": s_fg, "FT": s_ft, "OR": oreb, "DR": dreb, "TR": treb, "AS": ast, "ST": stl, "TO": tov, "BS": blk, "PF": pf, "EFF": eff, "+/-": pm})
    if team_stats_official:
        t_off = team_stats_official; team_pts = safe_int(t_off.get("points")) - sum_pts; team_or = safe_int(t_off.get("offensiveRebounds")) - sum_or; team_dr = safe_int(t_off.get("defensiveRebounds")) - sum_dr
        team_tr = safe_int(t_off.get("totalRebounds")) - sum_tr; team_as = safe_int(t_off.get("assists")) - sum_as; team_st = safe_int(t_off.get("steals")) - sum_st; team_to = safe_int(t_off.get("turnovers")) - sum_to
        team_bs = safe_int(t_off.get("blocks")) - sum_bs; team_pf = safe_int(t_off.get("foulsCommitted")) - sum_pf
        if (team_or != 0 or team_dr != 0 or team_tr != 0 or team_to != 0 or team_pf != 0 or team_pts != 0):
            data.append({"No.": "", "Name": "Team / Coach", "Min": "", "PTS": team_pts, "2P": "", "3P": "", "FG": "", "FT": "", "OR": team_or, "DR": team_dr, "TR": team_tr, "AS": team_as, "ST": team_st, "TO": team_to, "BS": team_bs, "PF": team_pf, "EFF": "", "+/-": ""})
    t_off = team_stats_official if team_stats_official else {}
    final_pts = safe_int(t_off.get("points")) if t_off else sum_pts; final_fgm = safe_int(t_off.get("fieldGoalsMade")) if t_off else sum_fgm; final_fga = safe_int(t_off.get("fieldGoalsAttempted")) if t_off else sum_fga
    final_3pm = safe_int(t_off.get("threePointShotsMade")) if t_off else sum_3pm; final_3pa = safe_int(t_off.get("threePointShotsAttempted")) if t_off else sum_3pa; final_ftm = safe_int(t_off.get("freeThrowsMade")) if t_off else sum_ftm
    final_fta = safe_int(t_off.get("freeThrowsAttempted")) if t_off else sum_fta
    tot_fg_pct = int(final_fgm/final_fga*100) if final_fga else 0; tot_3p_pct = int(final_3pm/final_3pa*100) if final_3pa else 0; tot_ft_pct = int(final_ftm/final_fta*100) if final_fta else 0
    totals = {"No.": "", "Name": "TOTALS", "Min": "200:00", "PTS": final_pts, "2P": "", "3P": f"{final_3pm}/{final_3pa} ({tot_3p_pct}%)", "FG": f"{final_fgm}/{final_fga} ({tot_fg_pct}%)", "FT": f"{final_ftm}/{final_fta} ({tot_ft_pct}%)", "OR": safe_int(t_off.get("offensiveRebounds")) if t_off else sum_or, "DR": safe_int(t_off.get("defensiveRebounds")) if t_off else sum_dr, "TR": safe_int(t_off.get("totalRebounds")) if t_off else sum_tr, "AS": safe_int(t_off.get("assists")) if t_off else sum_as, "ST": safe_int(t_off.get("steals")) if t_off else sum_st, "TO": safe_int(t_off.get("turnovers")) if t_off else sum_to, "BS": safe_int(t_off.get("blocks")) if t_off else sum_bs, "PF": safe_int(t_off.get("foulsCommitted")) if t_off else sum_pf, "EFF": safe_int(t_off.get("efficiency")) if t_off else sum_eff, "+/-": ""}
    data.append(totals)
    df = pd.DataFrame(data)
    def highlight_totals(row):
        if row['Name'] == 'TOTALS': return ['font-weight: bold; background-color: #f0f0f0' for _ in row]
        if row['Name'] == 'Team / Coach': return ['font-style: italic; color: #555;' for _ in row]
        return ['' for _ in row]
    st.markdown(f"#### {team_name}"); calc_height = (len(df) + 1) * 35 + 3; st.dataframe(df.style.apply(highlight_totals, axis=1), hide_index=True, use_container_width=True, height=calc_height)
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
    q_h = [res.get(f"homeTeamQ{i}Score", 0) for i in range(1, 5)]; q_g = [res.get(f"guestTeamQ{i}Score", 0) for i in range(1, 5)]; h_q_wins = sum(1 for i in range(4) if q_h[i] > q_g[i])
    if h_q_wins == 4 and s_h > s_g: text += f"{h_name} gewann dabei jedes einzelne Viertel. "
    elif h_q_wins == 0 and s_h < s_g: text += f"{g_name} ließ nichts anbrennen und entschied alle vier Viertel für sich. "
    def get_best(p_list, key):
        if not p_list: return None, 0
        s = sorted(p_list, key=lambda x: safe_int(x.get(key)), reverse=True); p = s[0]; return p.get("seasonPlayer", {}).get("lastName", "Unknown"), safe_int(p.get(key))
    h_p, h_v = get_best(h_data.get("playerStats", []), "points"); g_p, g_v = get_best(g_data.get("playerStats", []), "points")
    text += f"\n\n**Top Performer:**\nAuf Seiten von {h_name} war **{h_p}** mit {h_v} Punkten am erfolgreichsten. Bei {g_name} hielt **{g_p}** mit {g_v} Zählern dagegen."
    return text

def generate_complex_ai_prompt(box):
    if not box: return "Keine Daten."
    h_data = box.get("homeTeam", {}); g_data = box.get("guestTeam", {}); h_name = get_team_name(h_data, "Heim"); g_name = get_team_name(g_data, "Gast"); res = box.get("result", {}); pbp_summary = analyze_game_flow(box.get("actions", []), h_name, g_name)
    def get_stats_str(team_data):
        s = team_data.get("gameStat", {}); p_list = team_data.get("playerStats", []); top_p = sorted([p for p in p_list if p.get("points", 0) is not None], key=lambda x: x.get("points", 0), reverse=True)[:2]; top_str = ", ".join([f"{p.get('seasonPlayer', {}).get('lastName')} ({p.get('points')} Pkt)" for p in top_p])
        return f"FG: {safe_int(s.get('fieldGoalsSuccessPercent'))}%, Reb: {safe_int(s.get('totalRebounds'))}, TO: {safe_int(s.get('turnovers'))}, Top: {top_str}"
    prompt = f"""Erstelle 3 journalistische Spielberichte (Heim-Sicht, Neutral, Gäste-Sicht) basierend auf diesen Daten:\nHeim: {h_name}, Gast: {g_name}, Ergebnis: {res.get('homeTeamFinalScore')} : {res.get('guestTeamFinalScore')}\nViertel: Q1 {res.get('homeTeamQ1Score')}:{res.get('guestTeamQ1Score')}, Q2 {res.get('homeTeamQ2Score')}:{res.get('guestTeamQ2Score')}, Q3 {res.get('homeTeamQ3Score')}:{res.get('guestTeamQ3Score')}, Q4 {res.get('homeTeamQ4Score')}:{res.get('guestTeamQ4Score')}\nStats Heim: {get_stats_str(h_data)}\nStats Gast: {get_stats_str(g_data)}\nZuschauer: {res.get('spectators', 'k.A.')}, Halle: {box.get('venue', {}).get('name', 'Halle')}\n\nSPIELVERLAUF (PBP):\n{pbp_summary}\n\nANWEISUNGEN:\nSchreibe lebendig, emotional und detailreich. Nutze die PBP-Daten für Crunchtime-Beschreibung."""
    return prompt

def run_openai_generation(api_key, prompt):
    client = openai.OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": "Du bist ein Sportjournalist."}, {"role": "user", "content": prompt}], temperature=0.7)
        return response.choices[0].message.content
    except Exception as e: return f"Fehler: {str(e)}"

# --- NEUE FUNKTIONEN FÜR PREP & LIVE ---

def render_prep_dashboard(team_id, team_name, df_roster, last_games, metadata_callback=None):
    st.subheader(f"Analyse: {team_name}")
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.markdown("#### Top 4 Spieler (nach PPG)")
        if df_roster is not None and not df_roster.empty:
            top4 = df_roster.sort_values(by="PPG", ascending=False).head(4)
            for _, row in top4.iterrows():
                with st.container():
                    col_img, col_stats = st.columns([1, 4])
                    with col_img:
                        if "img" in row.index and row["img"]:
                            st.image(row["img"], width=100)
                        elif metadata_callback:
                            # Callback nutzen um Bild zu laden
                            meta = metadata_callback(row["PLAYER_ID"])
                            if meta["img"]: st.image(meta["img"], width=100)
                            else: st.markdown(f"<div style='font-size:30px; text-align:center;'>👤</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<div style='font-size:30px; text-align:center;'>👤</div>", unsafe_allow_html=True)

                    with col_stats:
                        st.markdown(f"**#{row['NR']} {row['NAME_FULL']}**")
                        # Fallback für Age/Nat, falls im DataFrame leer
                        age = row.get('AGE', '-')
                        nat = row.get('NATIONALITY', '-')
                        height = row.get('HEIGHT', '-')
                        pos = row.get('POS', '-')

                        # Wenn leer, versuche Metadaten nachzuladen
                        if (age == '-' or nat == '-') and metadata_callback:
                             meta = metadata_callback(row["PLAYER_ID"])
                             if age == '-': age = meta.get('age', '-')
                             if nat == '-': nat = meta.get('nationality', '-')
                             if height == '-': height = meta.get('height', '-')
                             if pos == '-': pos = meta.get('pos', '-')

                        st.caption(f"Alter: {age} | Nat: {nat} | Größe: {height} | Pos: {pos}")
                        st.markdown(f"**PPG: {row['PPG']}** | FG%: {row['FG%']} | 3P%: {row['3PCT']}% | REB: {row['TOT']} | AST: {row['AS']}")
                    st.divider()
        else: st.warning("Keine Kaderdaten.")

    with c2:
        st.markdown("#### Formkurve")
        if last_games:
            played_games = [g for g in last_games if g.get('has_result')]
            # Sortierlogik für DD.MM.YYYY
            def parse_date(d_str):
                try: return datetime.strptime(d_str, "%d.%m.%Y %H:%M")
                except: return datetime.min
            
            games_sorted = sorted(played_games, key=lambda x: parse_date(x['date']), reverse=True)[:5]
            if games_sorted:
                # Kompakte Badges-Anzeige
                st.write("") # Spacer
                cols_form = st.columns(len(games_sorted))
                for idx, g in enumerate(games_sorted):
                    h_score = g.get('home_score', 0)
                    g_score = g.get('guest_score', 0)
                    is_home = (g.get('homeTeamId') == str(team_id))
                    
                    win = False
                    if is_home and h_score > g_score: win = True
                    elif not is_home and g_score > h_score: win = True
                    
                    color = "#28a745" if win else "#dc3545" # Grün/Rot
                    char = "W" if win else "L"
                    
                    with cols_form[idx]:
                        st.markdown(f"<div style='background-color:{color};color:white;text-align:center;padding:10px;border-radius:5px;font-weight:bold;' title='{g['date']}\n{g['home']} vs {g['guest']}\n{g['score']}'>{char}</div>", unsafe_allow_html=True)
            else: st.info("Keine gespielten Spiele.")
        else: st.info("Keine Spiele.")

def create_live_boxscore_df(team_data):
    """Erstellt einen detaillierten DataFrame für den Live-Boxscore."""
    stats = []
    players = team_data.get("playerStats", [])
    
    for p in players:
        # Sekunden in mm:ss umwandeln
        sec = safe_int(p.get("secondsPlayed"))
        min_str = f"{sec // 60:02d}:{sec % 60:02d}"
        
        # Wurfquoten berechnen
        fgm = safe_int(p.get("fieldGoalsMade"))
        fga = safe_int(p.get("fieldGoalsAttempted"))
        fg_str = f"{fgm}/{fga}"
        fg_pct = (fgm / fga) if fga > 0 else 0.0

        m3 = safe_int(p.get("threePointShotsMade"))
        a3 = safe_int(p.get("threePointShotsAttempted"))
        p3_str = f"{m3}/{a3}"
        p3_pct = (m3 / a3) if a3 > 0 else 0.0
        
        ftm = safe_int(p.get("freeThrowsMade"))
        fta = safe_int(p.get("freeThrowsAttempted"))
        ft_str = f"{ftm}/{fta}"
        ft_pct = (ftm / fta) if fta > 0 else 0.0

        # On Court Logic (Versuche verschiedene Flags)
        is_on_court = p.get("onCourt", False) or p.get("isOnCourt", False)
        # Fallback auf Starter, falls onCourt nicht verfügbar (um wenigstens etwas zu markieren)
        # Wenn API onCourt nicht liefert, bleibt is_on_court False, es sei denn wir wollen Starter markieren
        is_starter = p.get("isStartingFive", False)

        stats.append({
            "#": p.get("seasonPlayer", {}).get("shirtNumber", "-"),
            "Name": p.get("seasonPlayer", {}).get("lastName", "Unk"),
            "Min": min_str,
            "PTS": safe_int(p.get("points")),
            "FG": fg_str,
            "FG%": fg_pct,
            "3P": p3_str,
            "3P%": p3_pct,
            "FT": ft_str,
            "FT%": ft_pct,
            "OR": safe_int(p.get("offensiveRebounds")),
            "DR": safe_int(p.get("defensiveRebounds")),
            "TR": safe_int(p.get("totalRebounds")),
            "AS": safe_int(p.get("assists")),
            "TO": safe_int(p.get("turnovers")),
            "ST": safe_int(p.get("steals")),
            "BS": safe_int(p.get("blocks")),
            "PF": safe_int(p.get("foulsCommitted")),
            "+/-": safe_int(p.get("plusMinus")),
            "OnCourt": is_on_court,
            "Starter": is_starter
        })
    
    df = pd.DataFrame(stats)
    if not df.empty:
        # Sortieren: Wer auf dem Feld ist oben, dann nach Punkten (optional)
        # Hier sortieren wir klassisch nach Punkten
        df = df.sort_values(by=["PTS", "Min"], ascending=[False, False])
    return df

def render_live_view(box):
    if not box: return
    h_name = get_team_name(box.get("homeTeam", {}), "Heim")
    g_name = get_team_name(box.get("guestTeam", {}), "Gast")
    res = box.get("result", {})
    
    s_h = res.get('homeTeamFinalScore', 0)
    s_g = res.get('guestTeamFinalScore', 0)
    period = res.get('period') or box.get('period')
    
    # Try getting score from last action if main result is 0-0
    actions = box.get("actions", [])
    if s_h == 0 and s_g == 0 and actions:
        last = actions[-1]
        if last.get('homeTeamPoints') is not None: s_h = last.get('homeTeamPoints')
        if last.get('guestTeamPoints') is not None: s_g = last.get('guestTeamPoints')
        if last.get('period'): period = last.get('period')

    # Mapping für Perioden-Anzeige
    p_map = {1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"}
    if safe_int(period) > 4: p_str = f"OT{safe_int(period)-4}"
    else: p_str = p_map.get(safe_int(period), f"Q{safe_int(period)}") if period else "-"

    # Zeit
    gt = box.get('gameTime')
    if not gt and actions: gt = actions[-1].get('gameTime')
    time_disp = convert_elapsed_to_remaining(gt, period) if gt else "10:00"
    
    # Details extrahieren (Venue, Coaches, Datum)
    venue_name = box.get('venue', {}).get('name', '-')
    venue_addr = box.get('venue', {}).get('address', '')
    if venue_addr: venue_name += f" ({venue_addr.split(',')[-1].strip()})"
    
    date_str = format_date_time(box.get('scheduledTime'))
    
    # Refs
    refs = []
    for i in range(1, 4):
        r = box.get(f"referee{i}")
        if r and isinstance(r, dict): refs.append(f"{r.get('lastName')} {r.get('firstName')}")
    ref_str = ", ".join(refs) if refs else "-"

    # Coaches
    h_coach = box.get("homeTeam", {}).get("headCoachName")
    if not h_coach: h_coach = box.get("homeTeam", {}).get("headCoach", {}).get("lastName", "-")
    
    g_coach = box.get("guestTeam", {}).get("headCoachName")
    if not g_coach: g_coach = box.get("guestTeam", {}).get("headCoach", {}).get("lastName", "-")
    
    # Header Anzeige
    st.markdown(f"""<div style='text-align:center;background:#222;color:#fff;padding:15px;border-radius:10px;margin-bottom:20px;box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
    <div style='font-size:1em; color:#bbb; margin-bottom:5px;'>{date_str} @ {venue_name}</div>
    <div style='font-size:1.4em; margin-bottom:5px; font-weight:bold;'>{h_name} <span style='font-size:0.6em; font-weight:normal; color:#aaa;'>(HC: {h_coach})</span></div>
    <div style='font-size:3.5em;font-weight:bold;line-height:1;'>{s_h} : {s_g}</div>
    <div style='font-size:1.4em; margin-top:5px; font-weight:bold;'>{g_name} <span style='font-size:0.6em; font-weight:normal; color:#aaa;'>(HC: {g_coach})</span></div>
    <div style='color:#ffcc00; font-weight:bold; font-size:1.4em; margin-top:10px;'>{p_str} | {time_disp}</div>
    <div style='font-size:0.8em; color:#666; margin-top:5px;'>Refs: {ref_str}</div>
    </div>""", unsafe_allow_html=True)

    # Tabs für Boxscore und Ticker
    tab_stats, tab_pbp = st.tabs(["📊 Live Boxscore & Stats", "📜 Play-by-Play"])

    with tab_stats:
        # DATA FRAMES ERSTELLEN
        df_h = create_live_boxscore_df(box.get("homeTeam", {}))
        df_g = create_live_boxscore_df(box.get("guestTeam", {}))

        # Config für Spalten
        col_cfg = {
            "#": st.column_config.TextColumn("#", width="small"),
            "Name": st.column_config.TextColumn("Name", width="medium"),
            "Min": st.column_config.TextColumn("Min", width="small"),
            "PTS": st.column_config.ProgressColumn("Pkt", min_value=0, max_value=40, format="%d"),
            "FG": st.column_config.TextColumn("FG", width="small"),
            "FG%": st.column_config.ProgressColumn("FG%", min_value=0, max_value=1, format="%.2f"),
            "3P": st.column_config.TextColumn("3P", width="small"),
            "3P%": st.column_config.ProgressColumn("3P%", min_value=0, max_value=1, format="%.2f"),
            "FT": st.column_config.TextColumn("FW", width="small"),
            "FT%": st.column_config.ProgressColumn("FW%", min_value=0, max_value=1, format="%.2f"),
            "OnCourt": st.column_config.CheckboxColumn("Court", disabled=True),
            "Starter": st.column_config.CheckboxColumn("Start", disabled=True),
        }
        
        # Helper zum Stylen (Highlight OnCourt oder Starter)
        def highlight_active(row):
            # Wenn OnCourt True ist, grün färben. Sonst wenn Starter, leicht grau.
            if row.get("OnCourt"):
                return ['background-color: #d4edda; color: #155724'] * len(row)
            elif row.get("Starter"):
                return ['background-color: #f8f9fa; font-weight: bold'] * len(row)
            return [''] * len(row)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"### {h_name}")
            if not df_h.empty:
                # Spalten filtern für Anzeige
                cols_show = ["#", "Name", "Min", "PTS", "FG", "FG%", "3P", "3P%", "TR", "AS", "TO", "PF", "+/-"]
                # Höhe berechnen (ca 35px pro Zeile + Header)
                height_h = (len(df_h) + 1) * 35 + 3
                st.dataframe(df_h[cols_show].style.apply(highlight_active, axis=1), column_config=col_cfg, hide_index=True, use_container_width=True, height=height_h)
            else: st.info("Keine Daten")
            
        with c2:
            st.markdown(f"### {g_name}")
            if not df_g.empty:
                cols_show = ["#", "Name", "Min", "PTS", "FG", "FG%", "3P", "3P%", "TR", "AS", "TO", "PF", "+/-"]
                height_g = (len(df_g) + 1) * 35 + 3
                st.dataframe(df_g[cols_show].style.apply(highlight_active, axis=1), column_config=col_cfg, hide_index=True, use_container_width=True, height=height_g)
            else: st.info("Keine Daten")

        st.divider()
        st.subheader("📈 Team Vergleich")
        
        # Aggregierte Team Stats berechnen
        def get_team_totals(df):
            if df.empty: return {"PTS":0, "REB":0, "AST":0, "TO":0, "STL":0, "BLK":0, "PF":0}
            return {
                "PTS": df["PTS"].sum(), "REB": df["TR"].sum(), "AST": df["AS"].sum(),
                "TO": df["TO"].sum(), "STL": df["ST"].sum(), "BLK": df["BS"].sum(),
                "PF": df["PF"].sum()
            }
        
        t_h = get_team_totals(df_h)
        t_g = get_team_totals(df_g)
        
        # Daten für Chart aufbereiten
        chart_data = []
        metrics = ["PTS", "REB", "AST", "TO", "STL", "PF"]
        for m in metrics:
            chart_data.append({"Team": h_name, "Metric": m, "Value": t_h[m]})
            chart_data.append({"Team": g_name, "Metric": m, "Value": t_g[m]})
            
        df_chart = pd.DataFrame(chart_data)
        
        # Altair Chart
        chart = alt.Chart(df_chart).mark_bar().encode(
            x=alt.X('Metric', title=None, sort=metrics),
            y=alt.Y('Value', title=None),
            color=alt.Color('Team', title="Team"),
            xOffset='Team',
            tooltip=['Team', 'Metric', 'Value']
        ).properties(height=300)
        
        st.altair_chart(chart, use_container_width=True)

    with tab_pbp:
        st.subheader("📜 Live Ticker")
        render_full_play_by_play(box, height=600)

def analyze_scouting_data(team_id, detailed_games):
    """
    Analysiert eine Liste von Spielen (JSON) auf Scouting-Aspekte.
    """
    stats = {
        "games_count": len(detailed_games),
        "wins": 0,
        "ato_stats": {"possessions": 0, "points": 0, "score_pct": 0}, # After Time Out
        "start_stats": {"pts_diff_first_5min": 0},
        "top_scorers": {},
        "rotation_depth": 0
    }
    
    tid_str = str(team_id)
    
    for box in detailed_games:
        # 1. Win/Loss Check
        h_id = str(box.get("homeTeam", {}).get("seasonTeamId"))
        res = box.get("result", {})
        if not res: 
             # Fallback falls Result nicht im Boxscore Objekt
             res = {"homeTeamFinalScore": 0, "guestTeamFinalScore": 0} 
             # Wir verlassen uns hier drauf, dass fetch_last_n_games_complete das gefixt hat oder API Daten da sind

        s_h = safe_int(res.get("homeTeamFinalScore") or box.get("homeTeamPoints")) # Fallback
        s_g = safe_int(res.get("guestTeamFinalScore") or box.get("guestTeamPoints"))

        is_home = (h_id == tid_str)
        if (is_home and s_h > s_g) or (not is_home and s_g > s_h):
            stats["wins"] += 1
            
        # 2. Player Stats Aggregation (für Top Scorer)
        # Wir suchen das korrekte Team Objekt
        team_obj = box.get("homeTeam") if is_home else box.get("guestTeam")
        if team_obj:
            players = team_obj.get("playerStats", [])
            active_players = 0
            for p in players:
                pid = p.get("seasonPlayer", {}).get("id")
                name = p.get("seasonPlayer", {}).get("lastName", "Unk")
                pts = safe_int(p.get("points"))
                sec = safe_int(p.get("secondsPlayed"))
                
                if sec > 300: active_players += 1 # Mind. 5 Min gespielt für Rotation
                
                if pid not in stats["top_scorers"]: stats["top_scorers"][pid] = {"name": name, "pts": 0, "games": 0}
                stats["top_scorers"][pid]["pts"] += pts
                stats["top_scorers"][pid]["games"] += 1
            
            stats["rotation_depth"] += active_players

        # 3. PBP Analyse (ATO & Start)
        actions = box.get("actions", [])
        # Sortieren
        actions.sort(key=lambda x: x.get('actionNumber', 0))
        
        # A) Spielstart (Erste 5 Minuten Q1)
        # Wir berechnen das Delta in den ersten 5 Minuten
        start_score_h = 0; start_score_g = 0
        for act in actions:
            # Check Q1 und Zeit (10 Min - 5 Min = 5 Min Rest)
            if act.get("period") != 1: break
            
            # Score update
            h_p = act.get("homeTeamPoints")
            g_p = act.get("guestTeamPoints")
            if h_p is not None: start_score_h = safe_int(h_p)
            if g_p is not None: start_score_g = safe_int(g_p)
            
            # Vereinfachung: Wir schauen uns den Score nach ca. 20 Aktionen im 1. Viertel an (grobe Schätzung für 5 min)
            if safe_int(act.get("actionNumber")) > 25: break 
            
        diff = start_score_h - start_score_g if is_home else start_score_g - start_score_h
        stats["start_stats"]["pts_diff_first_5min"] += diff

        # B) ATO (After Timeout)
        # Suche nach Timeout UNSERES Teams
        for i, act in enumerate(actions):
            if act.get("type") == "TIMEOUT" and str(act.get("seasonTeamId")) == tid_str:
                # Timeout gefunden. Analysiere die nächsten 3 Events auf Punkte
                stats["ato_stats"]["possessions"] += 1
                
                # Suche das nächste Scoring Event oder Turnover
                # Wir schauen maximal 5 Aktionen weiter
                found_result = False
                for j in range(1, 6):
                    if i + j >= len(actions): break
                    next_act = actions[i+j]
                    
                    # Wenn Punkte erzielt wurden
                    pts = safe_int(next_act.get("points"))
                    act_tid = str(next_act.get("seasonTeamId"))
                    
                    if pts > 0 and act_tid == tid_str:
                        stats["ato_stats"]["points"] += pts
                        found_result = True
                        break
                    
                    # Wenn Gegner punktet oder wir Turnover machen -> Possession vorbei ohne Punkte
                    if (pts > 0 and act_tid != tid_str) or (next_act.get("type") == "TURNOVER" and act_tid == tid_str):
                        found_result = True
                        break
                
                # Wenn wir Punkte gemacht haben, zählt es als Erfolg
                # (Punkte wurden oben addiert)

    # Averages berechnen
    cnt = stats["games_count"] if stats["games_count"] > 0 else 1
    stats["rotation_depth"] = round(stats["rotation_depth"] / cnt, 1)
    stats["start_stats"]["avg_diff"] = round(stats["start_stats"]["pts_diff_first_5min"] / cnt, 1)
    
    # Top Scorers sortieren
    scorer_list = []
    for pid, data in stats["top_scorers"].items():
        avg = data["pts"] / data["games"]
        scorer_list.append({"name": data["name"], "ppg": round(avg, 1)})
    stats["top_scorers_list"] = sorted(scorer_list, key=lambda x: x["ppg"], reverse=True)[:5]

    return stats

def render_team_analysis_dashboard(team_id, team_name):
    # Import hier damit keine Zirkelbezüge entstehen
    from src.api import fetch_last_n_games_complete, get_best_team_logo
    
    logo = get_best_team_logo(team_id)
    c1, c2 = st.columns([1, 4])
    with c1:
        if logo: st.image(logo, width=100)
    with c2:
        st.title(f"Scouting Report: {team_name}")
        st.caption("Basierend auf der Play-by-Play Analyse der letzten 3 Spiele")

    with st.spinner(f"Analysiere die letzten Spiele von {team_name}..."):
        # Daten laden (letzte 3 Spiele reichen für Trend)
        games_data = fetch_last_n_games_complete(team_id, "2025", n=3)
        
        if not games_data:
            st.warning("Keine Spieldaten verfügbar.")
            return

        # Analyse durchführen
        scout = analyze_scouting_data(team_id, games_data)

    # --- UI RENDERING ---
    
    # 1. Key Facts Row
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Analysierte Spiele", scout["games_count"], f"{scout['wins']} Siege")
    
    # Start Verhalten
    start_val = scout["start_stats"]["avg_diff"]
    k2.metric("Start-Qualität (Q1)", f"{start_val:+.1f}", help="Durchschnittliche Punktedifferenz in den ersten 5 Minuten")
    
    # Rotation
    k3.metric("Rotation (Spieler >5min)", scout["rotation_depth"])
    
    # ATO Efficiency
    ato_pts = scout["ato_stats"]["points"]
    ato_poss = scout["ato_stats"]["possessions"]
    ato_ppp = round(ato_pts / ato_poss, 2) if ato_poss > 0 else 0.0
    k4.metric("ATO Effizienz", f"{ato_ppp} PPP", f"{ato_poss} Timeouts")

    st.divider()
    
    # 2. Detail Spalten
    c_left, c_right = st.columns([1, 1])
    
    with c_left:
        st.subheader("🔑 Schlüsselspieler (Last 3)")
        if scout["top_scorers_list"]:
            df_top = pd.DataFrame(scout["top_scorers_list"])
            st.dataframe(
                df_top, 
                column_config={
                    "name": "Name",
                    "ppg": st.column_config.ProgressColumn("PPG (Trend)", format="%.1f", min_value=0, max_value=30)
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("Keine Scorer Daten.")
            
        st.info("💡 **ATO (After Timeout):** Zeigt, wie gut das Team direkt nach einer Auszeit punktet (Points per Possession). Ein hoher Wert (>1.0) deutet auf gutes Coaching/Set-Plays hin.")

    with c_right:
        st.subheader("📅 Analysierte Spiele")
        for g in games_data:
            opp = g.get('meta_opponent', 'Gegner')
            res = g.get('meta_result', '-:-')
            date = g.get('meta_date', '')
            with st.expander(f"{date}: vs {opp} ({res})"):
                # Mini PBP Summary
                st.caption(analyze_game_flow(g.get("actions", []), get_team_name(g.get("homeTeam",{})), get_team_name(g.get("guestTeam",{}))))

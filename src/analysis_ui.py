import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import pytz

# Übersetzungswörterbuch für API-Begriffe
ACTION_TRANSLATION = {
    "TWO_POINT_SHOT_MADE": "2-Punkt Treffer",
    "TWO_POINT_SHOT_MISSED": "2-Punkt Fehlwurf",
    "THREE_POINT_SHOT_MADE": "3-Punkt Treffer",
    "THREE_POINT_SHOT_MISSED": "3-Punkt Fehlwurf",
    "FREE_THROW_MADE": "Freiwurf Treffer",
    "FREE_THROW_MISSED": "Freiwurf Fehlwurf",
    "REBOUND": "Rebound",
    "FOUL": "Foul",
    "TURNOVER": "Ballverlust",
    "ASSIST": "Assist",
    "STEAL": "Steal",
    "BLOCK": "Block",
    "SUBSTITUTION": "Wechsel",
    "TIMEOUT": "Auszeit",
    "JUMP_BALL": "Sprungball",
    "START": "Start",
    "END": "Ende",
    "TWO_POINT_THROW": "2-Punkt Wurf", 
    "THREE_POINT_THROW": "3-Punkt Wurf",
    "FREE_THROW": "Freiwurf",
    "layup": "Korbleger",
    "jump_shot": "Sprungwurf",
    "dunk": "Dunking",
    "offensive": "Offensiv",
    "defensive": "Defensiv",
    "personal_foul": "Persönlich",
    "technical_foul": "Technisch",
    "unsportsmanlike_foul": "Unsportlich",
    "half_or_far_distance": "Mitteldistanz/Fern",
    "close_distance": "Nahdistanz"
}

def translate_text(text):
    """Hilfsfunktion für einfache Übersetzungen."""
    if not text: return ""
    text_upper = str(text).upper()
    if text_upper in ACTION_TRANSLATION:
        return ACTION_TRANSLATION[text_upper]
    
    clean_text = text.replace("_", " ").lower()
    for eng, ger in ACTION_TRANSLATION.items():
        if eng.lower() in clean_text:
            clean_text = clean_text.replace(eng.lower(), ger)
    return clean_text.capitalize()

def safe_int(val):
    if val is None: return 0
    if isinstance(val, int): return val
    if isinstance(val, float): return int(val)
    if isinstance(val, str):
        if val.strip() == "": return 0
        try: return int(float(val))
        except: return 0
    return 0

def get_team_name(team_data, default_name="Team"):
    name = team_data.get("gameStat", {}).get("seasonTeam", {}).get("name")
    if name: return name
    name = team_data.get("seasonTeam", {}).get("name")
    if name: return name
    name = team_data.get("name")
    if name: return name
    return default_name

def format_date_time(iso_string):
    if not iso_string: return "-"
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        berlin = pytz.timezone("Europe/Berlin")
        dt_berlin = dt.astimezone(berlin)
        return dt_berlin.strftime("%d.%m.%Y | %H:%M Uhr")
    except:
        return iso_string

def get_player_lookup(box):
    """Erstellt ein Dictionary {id: 'Name'} für alle Spieler."""
    lookup = {}
    for team_key in ['homeTeam', 'guestTeam']:
        for p in box.get(team_key, {}).get('playerStats', []):
            pid = str(p.get('seasonPlayer', {}).get('id'))
            name = f"{p.get('seasonPlayer', {}).get('firstName', '')} {p.get('seasonPlayer', {}).get('lastName', '')}".strip()
            nr = p.get('seasonPlayer', {}).get('shirtNumber', '')
            lookup[pid] = f"#{nr} {name}"
    return lookup

def get_player_team_lookup(box):
    """
    Erstellt ein Dictionary {player_id: 'TeamName'}, um Aktionen einem Team zuzuordnen.
    """
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
    """
    Wandelt vergangene Zeit (Elapsed) in verbleibende Zeit (Remaining) um.
    Q1-Q4: Basis 10 Minuten. OT: Basis 5 Minuten.
    """
    if not time_str:
        return "-"
    
    # Standard: 10 Minuten pro Viertel
    base_minutes = 10
    # Wenn Period > 4, dann ist es Overtime -> 5 Minuten
    try:
        if int(period) > 4:
            base_minutes = 5
    except:
        pass # Fallback auf 10

    try:
        # Erwartetes Format: "00:09:25" (HH:MM:SS) oder "09:25"
        parts = time_str.split(":")
        elapsed_seconds = 0
        
        if len(parts) == 3: # HH:MM:SS
            elapsed_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2: # MM:SS
            elapsed_seconds = int(parts[0]) * 60 + int(parts[1])
        else:
            return time_str # Unbekanntes Format

        total_seconds = base_minutes * 60
        remaining_seconds = total_seconds - elapsed_seconds
        
        # Sicherstellen, dass wir nicht negativ werden (sollte nicht passieren, aber sicher ist sicher)
        if remaining_seconds < 0: remaining_seconds = 0
        
        # Zurück zu MM:SS
        rem_min = remaining_seconds // 60
        rem_sec = remaining_seconds % 60
        
        return f"{rem_min:02d}:{rem_sec:02d}"

    except Exception:
        return time_str # Bei Fehler Original zurückgeben

def render_full_play_by_play(box):
    """Rendert eine detaillierte Play-by-Play Tabelle auf Deutsch."""
    actions = box.get("actions", [])
    if not actions:
        st.info("Keine Play-by-Play Daten verfügbar.")
        return

    # Lookups erstellen
    player_map = get_player_lookup(box)
    player_team_map = get_player_team_lookup(box)
    
    home_name = get_team_name(box.get("homeTeam", {}), "Heim")
    guest_name = get_team_name(box.get("guestTeam", {}), "Gast")
    home_id = str(box.get("homeTeam", {}).get("seasonTeamId", "HOME"))
    guest_id = str(box.get("guestTeam", {}).get("seasonTeamId", "GUEST"))

    data = []
    
    running_h = 0
    running_g = 0

    for act in actions:
        # Score update
        h_pts = act.get("homeTeamPoints")
        g_pts = act.get("guestTeamPoints")
        
        if h_pts is not None: running_h = safe_int(h_pts)
        if g_pts is not None: running_g = safe_int(g_pts)
        
        score_str = f"{running_h} : {running_g}"
        
        # --- ZEIT LOGIK ---
        period = act.get("period", "")
        game_time = act.get("gameTime", "") # Format oft "00:01:23" (Elapsed)
        
        # Zeit umrechnen von Elapsed -> Remaining
        if game_time:
            display_time = convert_elapsed_to_remaining(game_time, period)
        else:
            display_time = "-"

        time_label = f"Q{period} {display_time}" if period else "-"
        
        # Akteur bestimmen
        pid = str(act.get("seasonPlayerId"))
        actor = player_map.get(pid, "")
        
        # Team bestimmen
        tid = str(act.get("seasonTeamId"))
        
        if tid == home_id:
            team_display = home_name
        elif tid == guest_id:
            team_display = guest_name
        elif pid in player_team_map: 
            team_display = player_team_map[pid]
        else:
            team_display = "-" 

        # Beschreibung & Übersetzung
        raw_type = act.get("type", "")
        action_german = translate_text(raw_type)
        
        is_successful = act.get("isSuccessful")
        if "Wurf" in action_german or "Freiwurf" in action_german or "Treffer" in action_german or "Fehlwurf" in action_german:
             if "Treffer" not in action_german and "Fehlwurf" not in action_german:
                 if is_successful is True:
                     action_german += " (Treffer)"
                 elif is_successful is False:
                     action_german += " (Fehlwurf)"

        qualifiers = act.get("qualifiers", [])
        if qualifiers:
            qual_german = [translate_text(q) for q in qualifiers]
            action_german += f" ({', '.join(qual_german)})"
        
        if act.get("points"):
            action_german += f" (+{act.get('points')})"

        data.append({
            "Zeit": time_label,
            "Score": score_str,
            "Team": team_display,
            "Spieler": actor,
            "Aktion": action_german
        })

    df = pd.DataFrame(data)
    
    rows = len(df)
    height = min((rows + 1) * 35 + 10, 1500) 
    
    st.dataframe(df, use_container_width=True, hide_index=True, height=height)

def calculate_advanced_stats_from_actions(actions, home_id, guest_id):
    stats = {
        "h_lead": 0, "g_lead": 0, "h_run": 0, "g_run": 0,
        "h_paint": 0, "g_paint": 0, "h_2nd": 0, "g_2nd": 0, "h_fb": 0, "g_fb": 0
    }
    if not actions: return stats

    cur_h = 0; cur_g = 0
    run_team = None; run_score = 0
    hid_str = str(home_id)

    for act in actions:
         new_h = safe_int(act.get("homeTeamPoints"))
         new_g = safe_int(act.get("guestTeamPoints"))
         
         if new_h == 0 and new_g == 0 and act.get("homeTeamPoints") is None:
             new_h = cur_h
             new_g = cur_g
         
         pts_h = new_h - cur_h
         pts_g = new_g - cur_g
         
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
             qualifiers = act.get("qualifiers", [])
             if isinstance(qualifiers, str): qualifiers = [qualifiers]
             q_str = " ".join([str(x).lower() for x in qualifiers])
             type_str = str(act.get("type", "")).lower()
             
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

def render_game_header(details):
    h_data = details.get("homeTeam", {})
    g_data = details.get("guestTeam", {})
    h_name = get_team_name(h_data, "Heim")
    g_name = get_team_name(g_data, "Gast")
    
    res = details.get("result", {})
    score_h = res.get("homeTeamFinalScore", 0)
    score_g = res.get("guestTeamFinalScore", 0)
    
    time_str = format_date_time(details.get("scheduledTime"))
    venue = details.get("venue", {})
    venue_str = venue.get("name", "-")
    address = venue.get("address", "")
    if address and isinstance(address, str):
        parts = address.split(",")
        if len(parts) > 1: venue_str += f", {parts[-1].strip()}"

    refs = []
    for i in range(1, 4):
        r = details.get(f"referee{i}")
        if r and isinstance(r, dict):
             fn = r.get("firstName", ""); ln = r.get("lastName", "")
             if fn or ln: refs.append(f"{ln} {fn}".strip())
             elif r.get("refId"): refs.append(f"Ref#{r.get('refId')}")
    ref_str = ", ".join(refs) if refs else "-"
    att = res.get("spectators", "-")
    
    st.markdown(f"<div style='text-align: center; color: #666; margin-bottom: 10px; font-size: 1.1em;'>📍 {venue_str} | 🕒 {time_str}</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([2, 1, 2])
    with c1:
        st.markdown(f"## {h_name}")
    with c2:
        st.markdown(f"<h1 style='text-align: center;'>{score_h} : {score_g}</h1>", unsafe_allow_html=True)
        q_data = {
            "Q1": [res.get("homeTeamQ1Score",0), res.get("guestTeamQ1Score",0)],
            "Q2": [res.get("homeTeamQ2Score",0), res.get("guestTeamQ2Score",0)],
            "Q3": [res.get("homeTeamQ3Score",0), res.get("guestTeamQ3Score",0)],
            "Q4": [res.get("homeTeamQ4Score",0), res.get("guestTeamQ4Score",0)]
        }
        if res.get("homeTeamOT1Score", 0) > 0 or res.get("guestTeamOT1Score", 0) > 0:
             q_data["OT"] = [res.get("homeTeamOT1Score",0), res.get("guestTeamOT1Score",0)]
        
        q_html = "<table style='width:100%; font-size:12px; border-collapse:collapse; margin:0 auto; text-align:center;'>"
        q_html += "<tr style='border-bottom:1px solid #ddd;'><th></th>" + "".join([f"<th>{k}</th>" for k in q_data.keys()]) + "</tr>"
        q_html += f"<tr><td style='font-weight:bold;'>{h_name[:3].upper()}</td>" + "".join([f"<td>{v[0]}</td>" for v in q_data.values()]) + "</tr>"
        q_html += f"<tr><td style='font-weight:bold;'>{g_name[:3].upper()}</td>" + "".join([f"<td>{v[1]}</td>" for v in q_data.values()]) + "</tr>"
        q_html += "</table>"
        st.markdown(q_html, unsafe_allow_html=True)

    with c3:
        st.markdown(f"## {g_name}")
    
    st.write("---")
    st.markdown(f"""
    <div style='display: flex; justify-content: space-between; color: #333; font-size: 14px; background-color: #f9f9f9; padding: 10px; border-radius: 5px;'>
        <span>👥 <b>Zuschauer:</b> {att}</span>
        <span>⚖️ <b>Schiedsrichter:</b> {ref_str}</span>
        <span>🆔 <b>Game ID:</b> {details.get('id', '-')}</span>
    </div>
    """, unsafe_allow_html=True)

def render_boxscore_table_pro(player_stats, team_stats_official, team_name, coach_name="-"):
    if not player_stats: return

    data = []
    # Summen-Variablen für Spieler
    sum_pts=0; sum_3pm=0; sum_3pa=0; sum_fgm=0; sum_fga=0; sum_ftm=0; sum_fta=0
    sum_or=0; sum_dr=0; sum_tr=0; sum_as=0; sum_st=0; sum_to=0; sum_bs=0; sum_pf=0; sum_eff=0; sum_pm=0

    for p in player_stats:
        info = p.get("seasonPlayer", {})
        name = f"{info.get('lastName', '')}, {info.get('firstName', '')}"
        nr = info.get("shirtNumber", "-")
        starter = "*" if p.get("isStartingFive") else ""
        sec = safe_int(p.get("secondsPlayed"))
        
        # Werte holen
        pts = safe_int(p.get("points")); sum_pts += pts
        m2 = safe_int(p.get("twoPointShotsMade")); a2 = safe_int(p.get("twoPointShotsAttempted"))
        p2 = safe_int(p.get("twoPointShotSuccessPercent"))
        m3 = safe_int(p.get("threePointShotsMade")); a3 = safe_int(p.get("threePointShotsAttempted"))
        p3 = safe_int(p.get("threePointShotSuccessPercent")); sum_3pm += m3; sum_3pa += a3
        mfg = safe_int(p.get("fieldGoalsMade")); afg = safe_int(p.get("fieldGoalsAttempted"))
        pfg = safe_int(p.get("fieldGoalsSuccessPercent")); sum_fgm += mfg; sum_fga += afg
        mft = safe_int(p.get("freeThrowsMade")); aft = safe_int(p.get("freeThrowsAttempted"))
        pft = safe_int(p.get("freeThrowsSuccessPercent")); sum_ftm += mft; sum_fta += aft
        oreb = safe_int(p.get("offensiveRebounds")); sum_or += oreb
        dreb = safe_int(p.get("defensiveRebounds")); sum_dr += dreb
        treb = safe_int(p.get("totalRebounds")); sum_tr += treb
        ast = safe_int(p.get("assists")); sum_as += ast
        stl = safe_int(p.get("steals")); sum_st += stl
        tov = safe_int(p.get("turnovers")); sum_to += tov
        blk = safe_int(p.get("blocks")); sum_bs += blk
        pf = safe_int(p.get("foulsCommitted")); sum_pf += pf
        eff = safe_int(p.get("efficiency")); sum_eff += eff
        pm = safe_int(p.get("plusMinus")); sum_pm += pm

        if sec > 0:
            min_str = f"{int(sec//60):02d}:{int(sec%60):02d}"
            s_2p = f"{m2}/{a2} ({int(p2)}%)" if a2 else ""
            s_3p = f"{m3}/{a3} ({int(p3)}%)" if a3 else ""
            s_fg = f"{mfg}/{afg} ({int(pfg)}%)"
            s_ft = f"{mft}/{aft} ({int(pft)}%)" if aft else ""
        else:
            min_str = "DNP"
            pts=0; s_2p=""; s_3p=""; s_fg=""; s_ft=""
            oreb=0; dreb=0; treb=0; ast=0; stl=0; tov=0; blk=0; pf=0; eff=0; pm=0

        data.append({
            "No.": f"{starter}{nr}", "Name": name, "Min": min_str, "PTS": pts,
            "2P": s_2p, "3P": s_3p, "FG": s_fg, "FT": s_ft,
            "OR": oreb, "DR": dreb, "TR": treb,
            "AS": ast, "ST": stl, "TO": tov, "BS": blk,
            "PF": pf, "EFF": eff, "+/-": pm
        })

    # --- TEAM / COACH ROW BERECHNUNG ---
    if team_stats_official:
        t_off = team_stats_official
        team_pts = safe_int(t_off.get("points")) - sum_pts
        team_or = safe_int(t_off.get("offensiveRebounds")) - sum_or
        team_dr = safe_int(t_off.get("defensiveRebounds")) - sum_dr
        team_tr = safe_int(t_off.get("totalRebounds")) - sum_tr
        team_as = safe_int(t_off.get("assists")) - sum_as
        team_st = safe_int(t_off.get("steals")) - sum_st
        team_to = safe_int(t_off.get("turnovers")) - sum_to
        team_bs = safe_int(t_off.get("blocks")) - sum_bs
        team_pf = safe_int(t_off.get("foulsCommitted")) - sum_pf
        
        if (team_or != 0 or team_dr != 0 or team_tr != 0 or team_to != 0 or team_pf != 0 or team_pts != 0):
            data.append({
                "No.": "", "Name": "Team / Coach", "Min": "", "PTS": team_pts if team_pts != 0 else 0,
                "2P": "", "3P": "", "FG": "", "FT": "",
                "OR": team_or, "DR": team_dr, "TR": team_tr,
                "AS": team_as, "ST": team_st, "TO": team_to, "BS": team_bs,
                "PF": team_pf, "EFF": "", "+/-": ""
            })

    # --- TOTALS ROW ---
    t_off = team_stats_official if team_stats_official else {}
    
    final_pts = safe_int(t_off.get("points")) if t_off else sum_pts
    final_fgm = safe_int(t_off.get("fieldGoalsMade")) if t_off else sum_fgm
    final_fga = safe_int(t_off.get("fieldGoalsAttempted")) if t_off else sum_fga
    final_3pm = safe_int(t_off.get("threePointShotsMade")) if t_off else sum_3pm
    final_3pa = safe_int(t_off.get("threePointShotsAttempted")) if t_off else sum_3pa
    final_ftm = safe_int(t_off.get("freeThrowsMade")) if t_off else sum_ftm
    final_fta = safe_int(t_off.get("freeThrowsAttempted")) if t_off else sum_fta
    
    tot_fg_pct = int(final_fgm/final_fga*100) if final_fga else 0
    tot_3p_pct = int(final_3pm/final_3pa*100) if final_3pa else 0
    tot_ft_pct = int(final_ftm/final_fta*100) if final_fta else 0
    
    totals = {
        "No.": "", "Name": "TOTALS", "Min": "200:00", "PTS": final_pts,
        "2P": "", 
        "3P": f"{final_3pm}/{final_3pa} ({tot_3p_pct}%)", 
        "FG": f"{final_fgm}/{final_fga} ({tot_fg_pct}%)", 
        "FT": f"{final_ftm}/{final_fta} ({tot_ft_pct}%)", 
        "OR": safe_int(t_off.get("offensiveRebounds")) if t_off else sum_or, 
        "DR": safe_int(t_off.get("defensiveRebounds")) if t_off else sum_dr, 
        "TR": safe_int(t_off.get("totalRebounds")) if t_off else sum_tr, 
        "AS": safe_int(t_off.get("assists")) if t_off else sum_as, 
        "ST": safe_int(t_off.get("steals")) if t_off else sum_st, 
        "TO": safe_int(t_off.get("turnovers")) if t_off else sum_to, 
        "BS": safe_int(t_off.get("blocks")) if t_off else sum_bs, 
        "PF": safe_int(t_off.get("foulsCommitted")) if t_off else sum_pf, 
        "EFF": safe_int(t_off.get("efficiency")) if t_off else sum_eff, 
        "+/-": ""
    }
    data.append(totals)
    df = pd.DataFrame(data)
    
    def highlight_totals(row):
        if row['Name'] == 'TOTALS':
            return ['font-weight: bold; background-color: #f0f0f0' for _ in row]
        if row['Name'] == 'Team / Coach':
            return ['font-style: italic; color: #555;' for _ in row]
        return ['' for _ in row]

    st.markdown(f"#### {team_name}")
    calc_height = (len(df) + 1) * 35 + 3
    st.dataframe(df.style.apply(highlight_totals, axis=1), hide_index=True, use_container_width=True, height=calc_height)
    if coach_name and coach_name != "-":
        st.markdown(f"*Head Coach: {coach_name}*")

def render_game_top_performers(box):
    h_data = box.get("homeTeam", {})
    g_data = box.get("guestTeam", {})
    h_name = get_team_name(h_data, "Heim")
    g_name = get_team_name(g_data, "Gast")

    def get_top3(stats_list, key="points"):
        active = [p for p in stats_list if safe_int(p.get("secondsPlayed")) > 0]
        sorted_p = sorted(active, key=lambda x: safe_int(x.get(key)), reverse=True)
        return sorted_p[:3]

    def mk_box(players, title, color, val_key="points"):
        html = f"<div style='flex:1; border:1px solid #ccc; margin:5px;'>"
        html += f"<div style='background:{color}; color:white; padding:5px; font-weight:bold; text-align:center;'>{title}</div>"
        html += "<table style='width:100%; border-collapse:collapse;'>"
        for p in players:
             info = p.get("seasonPlayer", {})
             name = f"{info.get('lastName', '')}"
             val = safe_int(p.get(val_key))
             html += f"<tr><td style='padding:6px; font-size:16px;'>{name}</td><td style='padding:6px; text-align:right; font-weight:bold; font-size:16px;'>{val}</td></tr>"
        html += "</table></div>"
        return html

    h_pts = get_top3(h_data.get("playerStats", []), "points")
    g_pts = get_top3(g_data.get("playerStats", []), "points")
    h_reb = get_top3(h_data.get("playerStats", []), "totalRebounds")
    g_reb = get_top3(g_data.get("playerStats", []), "totalRebounds")
    h_ast = get_top3(h_data.get("playerStats", []), "assists")
    g_ast = get_top3(g_data.get("playerStats", []), "assists")

    st.markdown("#### Top Performer")
    html = f"""
    <div style="display:flex; flex-direction:row; gap:10px; margin-bottom:20px;">
        {mk_box(h_pts, f"Points ({h_name})", "#e35b00", "points")}
        {mk_box(g_pts, f"Points ({g_name})", "#e35b00", "points")}
    </div>
    <div style="display:flex; flex-direction:row; gap:10px; margin-bottom:20px;">
        {mk_box(h_reb, f"Rebounds ({h_name})", "#0055ff", "totalRebounds")}
        {mk_box(g_reb, f"Rebounds ({g_name})", "#0055ff", "totalRebounds")}
    </div>
    <div style="display:flex; flex-direction:row; gap:10px;">
        {mk_box(h_ast, f"Assists ({h_name})", "#ffc107", "assists")}
        {mk_box(g_ast, f"Assists ({g_name})", "#ffc107", "assists")}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def render_charts_and_stats(box):
    h_data = box.get("homeTeam", {})
    g_data = box.get("guestTeam", {})
    h = h_data.get("gameStat", {})
    g = g_data.get("gameStat", {})
    h_name = get_team_name(h_data, "Heim")
    g_name = get_team_name(g_data, "Gast")

    # --- ADVANCED STATS ---
    actions = box.get("actions", [])
    hid = str(h_data.get("seasonTeam", {}).get("seasonTeamId", "0"))
    gid = str(g_data.get("seasonTeam", {}).get("seasonTeamId", "0"))
    calc_stats = calculate_advanced_stats_from_actions(actions, hid, gid)
    
    h_paint = calc_stats["h_paint"] if calc_stats["h_paint"] > 0 else "-"
    g_paint = calc_stats["g_paint"] if calc_stats["g_paint"] > 0 else "-"
    h_fb = calc_stats["h_fb"] if calc_stats["h_fb"] > 0 else "-"
    g_fb = calc_stats["g_fb"] if calc_stats["g_fb"] > 0 else "-"
    h_2nd = calc_stats["h_2nd"] if calc_stats["h_2nd"] > 0 else "-"
    g_2nd = calc_stats["g_2nd"] if calc_stats["g_2nd"] > 0 else "-"

    # --- CHARTS ---
    def mk_label(pct, made, att): return f"{pct}% ({made}/{att})"
    categories = ["Field Goals", "2 Points", "3 Points", "Free Throws"]
    
    h_vals = [
        {"Team": h_name, "Cat": "Field Goals", "Pct": safe_int(h.get('fieldGoalsSuccessPercent')), 
         "Label": mk_label(safe_int(h.get('fieldGoalsSuccessPercent')), safe_int(h.get('fieldGoalsMade')), safe_int(h.get('fieldGoalsAttempted')))},
        {"Team": h_name, "Cat": "2 Points", "Pct": safe_int(h.get('twoPointShotSuccessPercent')), 
         "Label": mk_label(safe_int(h.get('twoPointShotSuccessPercent')), safe_int(h.get('twoPointShotsMade')), safe_int(h.get('twoPointShotsAttempted')))},
        {"Team": h_name, "Cat": "3 Points", "Pct": safe_int(h.get('threePointShotSuccessPercent')), 
         "Label": mk_label(safe_int(h.get('threePointShotSuccessPercent')), safe_int(h.get('threePointShotsMade')), safe_int(h.get('threePointShotsAttempted')))},
        {"Team": h_name, "Cat": "Free Throws", "Pct": safe_int(h.get('freeThrowsSuccessPercent')), 
         "Label": mk_label(safe_int(h.get('freeThrowsSuccessPercent')), safe_int(h.get('freeThrowsMade')), safe_int(h.get('freeThrowsAttempted')))},
    ]
    g_vals = [
        {"Team": g_name, "Cat": "Field Goals", "Pct": safe_int(g.get('fieldGoalsSuccessPercent')), 
         "Label": mk_label(safe_int(g.get('fieldGoalsSuccessPercent')), safe_int(g.get('fieldGoalsMade')), safe_int(g.get('fieldGoalsAttempted')))},
        {"Team": g_name, "Cat": "2 Points", "Pct": safe_int(g.get('twoPointShotSuccessPercent')), 
         "Label": mk_label(safe_int(g.get('twoPointShotSuccessPercent')), safe_int(g.get('twoPointShotsMade')), safe_int(g.get('twoPointShotsAttempted')))},
        {"Team": g_name, "Cat": "3 Points", "Pct": safe_int(g.get('threePointShotSuccessPercent')), 
         "Label": mk_label(safe_int(g.get('threePointShotSuccessPercent')), safe_int(g.get('threePointShotsMade')), safe_int(g.get('threePointShotsAttempted')))},
        {"Team": g_name, "Cat": "Free Throws", "Pct": safe_int(g.get('freeThrowsSuccessPercent')), 
         "Label": mk_label(safe_int(g.get('freeThrowsSuccessPercent')), safe_int(g.get('freeThrowsMade')), safe_int(g.get('freeThrowsAttempted')))},
    ]
    
    source = pd.DataFrame(h_vals + g_vals)
    base = alt.Chart(source).encode(x=alt.X('Cat', sort=categories, title=None), xOffset='Team', y=alt.Y('Pct', title=None, axis=None))
    bar = base.mark_bar().encode(color=alt.Color('Team', legend=alt.Legend(title=None, orient='top')), tooltip=['Team', 'Cat', 'Label'])
    text = base.mark_text(dy=-10, color='black').encode(text='Label')
    chart = (bar + text).properties(height=350)

    metrics = [
        ("Offensive Rebounds", safe_int(h.get('offensiveRebounds')), safe_int(g.get('offensiveRebounds'))),
        ("Defensive Rebounds", safe_int(h.get('defensiveRebounds')), safe_int(g.get('defensiveRebounds'))),
        ("Total Rebounds", safe_int(h.get('totalRebounds')), safe_int(g.get('totalRebounds'))),
        ("Assists", safe_int(h.get("assists")), safe_int(g.get("assists"))),
        ("Fouls", safe_int(h.get("foulsCommitted")), safe_int(g.get("foulsCommitted"))),
        ("Turnovers", safe_int(h.get("turnovers")), safe_int(g.get("turnovers"))),
        ("Steals", safe_int(h.get("steals")), safe_int(g.get("steals"))),
        ("Blocks", safe_int(h.get("blocks")), safe_int(g.get("blocks"))),
        ("Points in Paint", h_paint, g_paint),
        ("2nd Chance Pts", h_2nd, g_2nd),
        ("Fastbreak Pts", h_fb, g_fb),
        ("Biggest Lead", calc_stats.get("h_lead", "-"), calc_stats.get("g_lead", "-")),
        ("Biggest Run", calc_stats.get("h_run", "-"), calc_stats.get("g_run", "-"))
    ]

    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown("#### Wurfquoten")
        st.altair_chart(chart, use_container_width=True)
    with c2:
        st.markdown("#### Team Statistik")
        html = f"""<table style="width:100%; border-collapse: collapse; font-family: sans-serif; font-size: 14px;">
<tr style="background-color:#003366; color:white;">
<th style="padding:8px; text-align:center; width:30%;">{h_name}</th>
<th style="padding:8px; text-align:center; width:40%;">Kategorie</th>
<th style="padding:8px; text-align:center; width:30%;">{g_name}</th>
</tr>"""
        for label, vh, vg in metrics:
            html += f"""<tr style="border-bottom:1px solid #eee;">
<td style="padding:6px; text-align:center;">{vh}</td>
<td style="padding:6px; text-align:center; font-weight:bold; color:#555;">{label}</td>
<td style="padding:6px; text-align:center;">{vg}</td>
</tr>"""
        html += "</table>"
        st.markdown(html, unsafe_allow_html=True)

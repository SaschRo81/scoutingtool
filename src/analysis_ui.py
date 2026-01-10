# --- START OF FILE src/analysis_ui.py ---
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

# --- NEU: VISUELLE STATISTIK-BALKEN ---

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
        .stat-container { margin-bottom: 15px; width: 100%; font-family: sans-serif; }
        .stat-label { text-align: center; font-weight: bold; font-style: italic; color: #555; font-size: 0.9em; margin-bottom: 2px; }
        .bar-wrapper { display: flex; align-items: center; justify-content: center; gap: 10px; height: 12px; }
        .bar-bg { background-color: #eee; flex-grow: 1; height: 100%; border-radius: 2px; position: relative; overflow: hidden; }
        .bar-fill-home { background-color: #e35b00; height: 100%; position: absolute; right: 0; transition: width 0.5s; }
        .bar-fill-guest { background-color: #333; height: 100%; position: absolute; left: 0; transition: width 0.5s; }
        .val-text { width: 80px; font-weight: bold; font-size: 0.95em; }
        .val-left { text-align: right; }
        .val-right { text-align: left; }
        .sub-val { font-size: 0.7em; color: #888; font-weight: normal; }
        </style>
    """, unsafe_allow_html=True)

    # Team Namen Header
    c1, c2, c3 = st.columns([1, 1, 1])
    c1.markdown(f"<h4 style='text-align:right; color:#e35b00;'>{h_name}</h4>", unsafe_allow_html=True)
    c2.write("")
    c3.markdown(f"<h4 style='text-align:left; color:#333;'>{g_name}</h4>", unsafe_allow_html=True)

    for label, key_made, key_att, is_pct in stats_to_show:
        h_val_main = safe_int(h_stat.get(key_made))
        g_val_main = safe_int(g_stat.get(key_made))
        
        h_disp = f"{h_val_main}"
        g_disp = f"{g_val_main}"
        
        h_fill_width = 0
        g_fill_width = 0

        if is_pct:
            h_a = safe_int(h_stat.get(key_att))
            g_a = safe_int(g_stat.get(key_att))
            h_p = get_pct(h_val_main, h_a)
            g_p = get_pct(g_val_main, g_a)
            h_disp = f"{h_p}% <span class='sub-val'>({h_val_main}/{h_a})</span>"
            g_disp = f"{g_p}% <span class='sub-val'>({g_val_main}/{g_a})</span>"
            h_fill_width = h_p
            g_fill_width = g_p
        else:
            # Für normale Stats: Balken relativ zum höheren Wert
            max_v = max(h_val_main, g_val_main, 1)
            h_fill_width = (h_val_main / max_v) * 100
            g_fill_width = (g_val_main / max_v) * 100

        st.markdown(f"""
            <div class="stat-container">
                <div class="stat-label">{label}</div>
                <div class="bar-wrapper">
                    <div class="val-text val-left">{h_disp}</div>
                    <div class="bar-bg"><div class="bar-fill-home" style="width: {h_fill_width}%;"></div></div>
                    <div class="bar-bg"><div class="bar-fill-guest" style="width: {g_fill_width}%;"></div></div>
                    <div class="val-text val-right">{g_disp}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

# --- STANDARD RENDERING ---

def render_full_play_by_play(box, height=600):
    actions = box.get("actions", [])
    if not actions: st.info("Keine Play-by-Play Daten verfügbar."); return
    player_map = get_player_lookup(box); player_team_map = {} # Lookup handled differently in live
    home_id = str(box.get("homeTeam", {}).get("seasonTeamId", "HOME"))
    guest_id = str(box.get("guestTeam", {}).get("seasonTeamId", "GUEST"))
    home_name = get_team_name(box.get("homeTeam", {}), "Heim")
    guest_name = get_team_name(box.get("guestTeam", {}), "Gast")
    data = []; running_h = 0; running_g = 0
    actions_sorted = sorted(actions, key=lambda x: x.get('actionNumber', 0))
    for act in actions_sorted:
        h_pts = act.get("homeTeamPoints"); g_pts = act.get("guestTeamPoints")
        if h_pts is not None: running_h = safe_int(h_pts); running_g = safe_int(g_pts)
        score_str = f"{running_h} : {running_g}"
        period = act.get("period", ""); game_time = act.get("gameTime", "") or act.get("timeInGame", "")
        display_time = convert_elapsed_to_remaining(game_time, period)
        time_label = f"Q{period} {display_time}" if period else "-"
        pid = str(act.get("seasonPlayerId")); actor = player_map.get(pid, ""); tid = str(act.get("seasonTeamId"))
        if tid == home_id: team_display = home_name
        elif tid == guest_id: team_display = guest_name
        else: team_display = "-" 
        raw_type = act.get("type", ""); action_german = translate_text(raw_type); is_successful = act.get("isSuccessful")
        if "Wurf" in action_german or "Freiwurf" in action_german or "Treffer" in action_german or "Fehlwurf" in action_german:
             if "Treffer" not in action_german and "Fehlwurf" not in action_german:
                 if is_successful is True: action_german += " (Treffer)"
                 elif is_successful is False: action_german += " (Fehlwurf)"
        qualifiers = act.get("qualifiers", [])
        if qualifiers: qual_german = [translate_text(q) for q in qualifiers]; action_german += f" ({', '.join(qual_german)})"
        if act.get("points"): action_german += f" (+{act.get('points')})"
        data.append({"Zeit": time_label, "Score": score_str, "Team": team_display, "Spieler": actor, "Aktion": action_german})
    df = pd.DataFrame(data)
    if not df.empty: df = df.iloc[::-1]
    st.dataframe(df, use_container_width=True, hide_index=True, height=height)

def create_live_boxscore_df(team_data):
    stats = []
    players = team_data.get("playerStats", [])
    for p in players:
        sec = safe_int(p.get("secondsPlayed")); min_str = f"{sec // 60:02d}:{sec % 60:02d}"
        fgm = safe_int(p.get("fieldGoalsMade")); fga = safe_int(p.get("fieldGoalsAttempted"))
        m3 = safe_int(p.get("threePointShotsMade")); a3 = safe_int(p.get("threePointShotsAttempted"))
        ftm = safe_int(p.get("freeThrowsMade")); fta = safe_int(p.get("freeThrowsAttempted"))
        is_on_court = p.get("onCourt", False) or p.get("isOnCourt", False); is_starter = p.get("isStartingFive", False)
        stats.append({"#": p.get("seasonPlayer", {}).get("shirtNumber", "-"), "Name": p.get("seasonPlayer", {}).get("lastName", "Unk"), "Min": min_str, "PTS": safe_int(p.get("points")), "FG": f"{fgm}/{fga}", "FG%": (fgm/fga) if fga>0 else 0.0, "3P": f"{m3}/{a3}", "3P%": (m3/a3) if a3>0 else 0.0, "FT": f"{ftm}/{fta}", "FT%": (ftm/fta) if fta>0 else 0.0, "TR": safe_int(p.get("totalRebounds")), "AS": safe_int(p.get("assists")), "TO": safe_int(p.get("turnovers")), "PF": safe_int(p.get("foulsCommitted")), "+/-": safe_int(p.get("plusMinus")), "OnCourt": is_on_court, "Starter": is_starter})
    df = pd.DataFrame(stats)
    if not df.empty: df = df.sort_values(by=["PTS", "Min"], ascending=[False, False])
    return df

def render_live_view(box):
    if not box: return
    h_name = get_team_name(box.get("homeTeam", {}), "Heim"); g_name = get_team_name(box.get("guestTeam", {}), "Gast")
    res = box.get("result", {}); s_h = res.get('homeTeamFinalScore', 0); s_g = res.get('guestTeamFinalScore', 0)
    period = res.get('period') or box.get('period')
    actions = box.get("actions", [])
    if s_h == 0 and s_g == 0 and actions:
        last = actions[-1]
        if last.get('homeTeamPoints') is not None: s_h = last.get('homeTeamPoints')
        if last.get('guestTeamPoints') is not None: s_g = last.get('guestTeamPoints')
        if not period: period = last.get('period')
    p_map = {1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"}
    if not period or period == 0:
        for act in reversed(actions):
            if act.get('period'): period = act.get('period'); break
    if safe_int(period) > 4: p_str = f"OT{safe_int(period)-4}"
    else: p_str = p_map.get(safe_int(period), f"Q{safe_int(period)}") if period else "-"
    gt = box.get('gameTime'); 
    if not gt and actions: gt = actions[-1].get('gameTime')
    time_disp = convert_elapsed_to_remaining(gt, period)
    v_name = box.get('venue', {}).get('name', '-'); v_addr = box.get('venue', {}).get('address', '')
    if v_addr: v_name += f" ({v_addr.split(',')[-1].strip()})"
    date_str = format_date_time(box.get('scheduledTime')); refs = []
    for i in range(1, 4):
        r = box.get(f"referee{i}")
        if r and isinstance(r, dict): refs.append(f"{r.get('lastName')} {r.get('firstName')}")
    ref_str = ", ".join(refs) if refs else "-"; h_coach = box.get("homeTeam", {}).get("headCoachName") or box.get("homeTeam", {}).get("headCoach", {}).get("lastName", "-")
    g_coach = box.get("guestTeam", {}).get("headCoachName") or box.get("guestTeam", {}).get("headCoach", {}).get("lastName", "-")
    st.markdown(f"<div style='text-align:center;background:#222;color:#fff;padding:15px;border-radius:10px;margin-bottom:20px;'><div style='font-size:1em; color:#bbb; margin-bottom:5px;'>{date_str} @ {v_name}</div><div style='font-size:1.4em; margin-bottom:5px; font-weight:bold;'>{h_name} <span style='font-size:0.6em; font-weight:normal; color:#aaa;'>(HC: {h_coach})</span></div><div style='font-size:3.5em;font-weight:bold;line-height:1;'>{s_h} : {s_g}</div><div style='font-size:1.4em; margin-top:5px; font-weight:bold;'>{g_name} <span style='font-size:0.6em; font-weight:normal; color:#aaa;'>(HC: {g_coach})</span></div><div style='color:#ffcc00; font-weight:bold; font-size:1.4em; margin-top:10px;'>{p_str} | {time_disp}</div><div style='font-size:0.8em; color:#666; margin-top:5px;'>Refs: {ref_str}</div></div>", unsafe_allow_html=True)
    
    # NEUE TABS
    tab_box, tab_match, tab_pbp = st.tabs(["📋 Boxscore", "📊 Team-Vergleich", "📜 Play-by-Play"])
    
    with tab_box:
        df_h = create_live_boxscore_df(box.get("homeTeam", {})); df_g = create_live_boxscore_df(box.get("guestTeam", {}))
        col_cfg = { "#": st.column_config.TextColumn("#", width="small"), "Name": st.column_config.TextColumn("Name", width="medium"), "Min": st.column_config.TextColumn("Min", width="small"), "PTS": st.column_config.ProgressColumn("Pkt", min_value=0, max_value=40, format="%d"), "FG": st.column_config.TextColumn("FG", width="small"), "FG%": st.column_config.ProgressColumn("FG%", min_value=0, max_value=1, format="%.2f"), "3P": st.column_config.TextColumn("3P", width="small"), "3P%": st.column_config.ProgressColumn("3P%", min_value=0, max_value=1, format="%.2f"), "FT": st.column_config.TextColumn("FW", width="small"), "FT%": st.column_config.ProgressColumn("FW%", min_value=0, max_value=1, format="%.2f"), "OnCourt": st.column_config.CheckboxColumn("Court", disabled=True), "Starter": st.column_config.CheckboxColumn("Start", disabled=True) }
        def highlight_active(row):
            if row.get("OnCourt"): return ['background-color: #d4edda; color: #155724'] * len(row)
            elif row.get("Starter"): return ['background-color: #f8f9fa; font-weight: bold'] * len(row)
            return [''] * len(row)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"### {h_name}")
            if not df_h.empty: st.dataframe(df_h[["#", "Name", "Min", "PTS", "FG", "FG%", "3P", "3P%", "TR", "AS", "TO", "PF", "+/-"]].style.apply(highlight_active, axis=1), column_config=col_cfg, hide_index=True, use_container_width=True, height=(len(df_h)+1)*35+3)
        with c2:
            st.markdown(f"### {g_name}")
            if not df_g.empty: st.dataframe(df_g[["#", "Name", "Min", "PTS", "FG", "FG%", "3P", "3P%", "TR", "AS", "TO", "PF", "+/-"]].style.apply(highlight_active, axis=1), column_config=col_cfg, hide_index=True, use_container_width=True, height=(len(df_g)+1)*35+3)
    
    with tab_match:
        render_live_comparison_bars(box)
        
    with tab_pbp:
        st.subheader("📜 Live Ticker")
        render_full_play_by_play(box, height=600)

# (Alle weiteren Scouting/Analyse-Funktionen bleiben hier unverändert...)
def analyze_scouting_data(team_id, detailed_games):
    stats = { "games_count": len(detailed_games), "wins": 0, "ato_stats": {"possessions": 0, "points": 0}, "start_stats": {"pts_diff_first_5min": 0}, "top_scorers": {}, "rotation_depth": 0 }
    tid_str = str(team_id)
    for box in detailed_games:
        is_home = box.get('meta_is_home', False)
        res = box.get("result", {})
        s_h = safe_int(res.get("homeTeamFinalScore") or box.get("homeTeamPoints"))
        s_g = safe_int(res.get("guestTeamFinalScore") or box.get("guestTeamPoints"))
        if (is_home and s_h > s_g) or (not is_home and s_g > s_h): stats["wins"] += 1
        team_obj = box.get("homeTeam") if is_home else box.get("guestTeam")
        if team_obj:
            active_players = 0
            for p in team_obj.get("playerStats", []):
                pid = p.get("seasonPlayer", {}).get("id"); pts = safe_int(p.get("points")); sec = safe_int(p.get("secondsPlayed"))
                if sec > 300: active_players += 1
                if pid not in stats["top_scorers"]: stats["top_scorers"][pid] = {"name": p.get("seasonPlayer", {}).get("lastName", "Unk"), "pts": 0, "games": 0}
                stats["top_scorers"][pid]["pts"] += pts; stats["top_scorers"][pid]["games"] += 1
            stats["rotation_depth"] += active_players
        actions = sorted(box.get("actions", []), key=lambda x: x.get('actionNumber', 0))
        start_h=0; start_g=0
        for act in actions:
            if act.get("period") != 1: break
            h_p = act.get("homeTeamPoints"); g_p = act.get("guestTeamPoints")
            if h_p is not None: start_h = safe_int(h_p)
            if g_p is not None: start_g = safe_int(g_p)
            if safe_int(act.get("actionNumber")) > 25: break 
        diff = start_h - start_g if is_home else start_g - start_h
        stats["start_stats"]["pts_diff_first_5min"] += diff
        home_tid = str(box.get("homeTeam", {}).get("seasonTeamId")); guest_tid = str(box.get("guestTeam", {}).get("seasonTeamId"))
        target_tid = home_tid if is_home else guest_tid
        for i, act in enumerate(actions):
            if "TIMEOUT" in str(act.get("type")).upper() and str(act.get("seasonTeamId")) == target_tid:
                stats["ato_stats"]["possessions"] += 1
                for j in range(1, 6):
                    if i + j >= len(actions): break
                    na = actions[i+j]; pts = safe_int(na.get("points")); act_tid = str(na.get("seasonTeamId"))
                    if pts > 0 and act_tid == target_tid: stats["ato_stats"]["points"] += pts; break
                    if (pts > 0 and act_tid != target_tid) or (na.get("type") == "TURNOVER" and na.get("seasonTeamId") == target_tid): break
    cnt = stats["games_count"] if stats["games_count"] > 0 else 1
    stats["rotation_depth"] = round(stats["rotation_depth"] / cnt, 1); stats["start_stats"]["avg_diff"] = round(stats["start_stats"]["pts_diff_first_5min"] / cnt, 1)
    scorer_list = []
    for pid, data in stats["top_scorers"].items(): 
        if data["games"] > 0: scorer_list.append({"name": data["name"], "ppg": round(data["pts"] / data["games"], 1)})
    stats["top_scorers_list"] = sorted(scorer_list, key=lambda x: x["ppg"], reverse=True)[:5]
    return stats

def prepare_ai_scouting_context(team_name, detailed_games, team_id):
    context = f"Scouting-Daten für Team: {team_name}\nAnzahl analysierter Spiele: {len(detailed_games)}\n\n"
    for g in detailed_games:
        is_home = g.get('meta_is_home', False)
        my_sid = str(g.get("homeTeam", {}).get("seasonTeamId")) if is_home else str(g.get("guestTeam", {}).get("seasonTeamId"))
        opp = g.get('meta_opponent', 'Gegner'); res = g.get('meta_result', 'N/A'); d_game = g.get('meta_date', 'Datum?')
        context += f"--- Spiel am {d_game} vs {opp} ({res}) ---\n"
        p_map = get_player_lookup(g); starters = []
        team_obj = g.get("homeTeam") if is_home else g.get("guestTeam")
        if team_obj:
            for p in team_obj.get("playerStats", []):
                if p.get("isStartingFive"): starters.append(p_map.get(str(p.get("seasonPlayer", {}).get("id")), "Unbekannt"))
        context += f"Starting 5: {', '.join(starters)}\n"
        actions = sorted(g.get("actions", []), key=lambda x: x.get('actionNumber', 0))
        closers = set()
        for act in reversed(actions):
            if len(closers) >= 5: break
            if str(act.get("seasonTeamId")) == my_sid:
                pid = str(act.get("seasonPlayerId"))
                if pid and pid != "None": closers.add(p_map.get(pid, "Unbekannt"))
        if closers: context += f"Closing Lineup: {', '.join(list(closers))}\n"
        context += "Start Phase (Q1 erste 12 Aktionen):\n"
        count = 0
        for act in actions:
            if act.get("period") == 1:
                tid = str(act.get("seasonTeamId")); actor = "WIR" if tid == my_sid else "GEGNER"
                pid = str(act.get("seasonPlayerId")); p_name = p_map.get(pid, "")
                if p_name and actor == "WIR": actor += f" ({p_name})"
                pts = act.get("points", 0); desc = translate_text(act.get("type", ""))
                if pts: desc += f" (+{pts} Pkt)"
                context += f"- {actor}: {desc}\n"; count += 1
                if count > 12: break
        context += "\nReaktionen nach Auszeiten (ATO):\n"; found_to = False
        for i, act in enumerate(actions):
            if "TIMEOUT" in str(act.get("type")).upper() and str(act.get("seasonTeamId")) == my_sid:
                found_to = True; context += f"TIMEOUT (WIR) genommen.\n"
                for j in range(1, 5):
                    if i+j < len(actions):
                        na = actions[i+j]; ntid = str(na.get("seasonTeamId")); who_act = "WIR" if ntid == my_sid else "GEGNER"
                        npid = str(na.get("seasonPlayerId")); np_name = player_map.get(npid, "")
                        if np_name and who_act == "WIR": who_act += f" ({np_name})"
                        ndesc = translate_text(na.get("type", "")); 
                        if na.get("points"): ndesc += f" (+{na.get('points')})"
                        context += f"  -> {who_act}: {ndesc}\n"
        if not found_to: context += "(Keine eigenen Timeouts gefunden)\n"
        context += "\n"
    return context

def render_team_analysis_dashboard(team_id, team_name):
    from src.api import fetch_last_n_games_complete, get_best_team_logo
    logo = get_best_team_logo(team_id)
    c1, c2 = st.columns([1, 4])
    with c1:
        if logo: st.image(logo, width=100)
    with c2:
        st.title(f"Scouting Report: {team_name}"); st.caption("Basierend auf der Play-by-Play Analyse der gesamten Saison")
    with st.spinner(f"Lade ALLE Spiele von {team_name}..."):
        games_data = fetch_last_n_games_complete(team_id, "2025", n=50)
        if not games_data: st.warning("Keine Spieldaten verfügbar."); return
        scout = analyze_scouting_data(team_id, games_data)
    k1, k2, k3, k4 = st.columns(4); k1.metric("Analysierte Spiele", scout["games_count"], f"{scout['wins']} Siege"); k2.metric("Start-Qualität (Q1)", f"{scout['start_stats']['avg_diff']:+.1f}"); k3.metric("Rotation", scout["rotation_depth"]); ato_ppp = round(scout["ato_stats"]["points"] / scout["ato_stats"]["possessions"], 2) if scout["ato_stats"]["possessions"] > 0 else 0.0; k4.metric("ATO Effizienz", f"{ato_ppp} PPP", f"{scout['ato_stats']['possessions']} TOs")
    st.divider(); col_left, col_right = st.columns([1, 1])
    with col_left:
        st.subheader("🔑 Schlüsselspieler"); 
        if scout["top_scorers_list"]: st.dataframe(pd.DataFrame(scout["top_scorers_list"]), hide_index=True, use_container_width=True)
        st.markdown("---"); st.subheader("🤖 KI-Prompt Generator"); st.info("Kopiere diesen Text in ChatGPT...")
        context_text = prepare_ai_scouting_context(team_name, games_data, team_id)
        prompt_full = f"Du bist ein professioneller Basketball-Scout. Analysiere {team_name}...\n\n{context_text}"
        st.code(prompt_full, language="text")
    with col_right:
        st.subheader("📅 Analysierte Spiele")
        for g in games_data:
            opp = g.get('meta_opponent', 'Gegner'); res = g.get('meta_result', '-:-')
            with st.expander(f"{g.get('meta_date')} vs {opp} ({res})"):
                st.caption(analyze_game_flow(g.get("actions", []), get_team_name(g.get("homeTeam",{})), get_team_name(g.get("guestTeam",{}))))

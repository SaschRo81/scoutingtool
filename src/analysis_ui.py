# --- START OF FILE src/analysis_ui.py ---
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import pytz
import openai 

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
                    
                    # Alter, Nation, Größe aus dem DataFrame
                    age = row.get('AGE', '-')
                    nat = row.get('NATIONALITY', '-')
                    height = row.get('HEIGHT_ROSTER', '-') 

                    img_url = None
                    if metadata_callback:
                        meta = metadata_callback(row["PLAYER_ID"])
                        if meta:
                            img_url = meta.get("img")

                    with col_img:
                        if img_url:
                            st.image(img_url, width=100)
                        else:
                            st.markdown(f"<div style='font-size:30px; text-align:center;'>👤</div>", unsafe_allow_html=True)

                    with col_stats:
                        st.markdown(f"**#{row['NR']} {row['NAME_FULL']}**")
                        st.caption(f"Alter: {age} | Nat: {nat} | Größe: {height}")
                        st.markdown(f"**PPG: {row['PPG']}** | FG%: {row['FG%']}% | 3P%: {row['3PCT']}% | REB: {row['TOT']} | AST: {row['AS']}")
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
                    h_score = g.get('home_score', 0)
                    g_score = g.get('guest_score', 0)
                    is_home = (g.get('homeTeamId') == str(team_id))
                    
                    win = (is_home and h_score > g_score) or (not is_home and g_score > h_score)
                    
                    color = "#28a745" if win else "#dc3545" 
                    char = "W" if win else "L"
                    
                    # FIX: Tooltip mit Spieldetails und Datum anzeigen
                    date_only = g['date'].split(' ')[0]
                    tooltip_text = f"{date_only} | {g['home']} vs {g['guest']} ({g['score']})"

                    with cols_form[idx]:
                        # Jedes Element in einen Container packen für den Tooltip
                        with st.container():
                            st.markdown(f"<div style='background-color:{color};color:white;text-align:center;padding:10px;border-radius:5px;font-weight:bold;' title='{tooltip_text}'>{char}</div>", unsafe_allow_html=True)
                            st.caption(f"{date_only}")
            else: st.info("Keine gespielten Spiele.")
        else: st.info("Keine Spiele.")

def render_live_view(box):
    # ... (Rest der Datei unverändert)
    pass 

def render_full_play_by_play(box, height=600):
    pass

def render_game_header(details):
    pass

def render_boxscore_table_pro(player_stats, team_stats_official, team_name, coach_name="-"):
    pass

def render_game_top_performers(box):
    pass

def render_charts_and_stats(box):
    pass

def generate_game_summary(box):
    pass

def generate_complex_ai_prompt(box):
    pass

def run_openai_generation(api_key, prompt):
    pass

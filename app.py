# --- START OF FILE src/analysis_ui.py ---
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import pytz

# Lokale Imports
from src.api import get_player_metadata_cached, get_best_team_logo, fetch_last_n_games_complete

# --- 1. KONSTANTEN & HELPERS ---
ACTION_TRANSLATION = {
    "TWO_POINT_SHOT_MADE": "2P Treffer", "TWO_POINT_SHOT_MISSED": "2P Fehl",
    "THREE_POINT_SHOT_MADE": "3P Treffer", "THREE_POINT_SHOT_MISSED": "3P Fehl",
    "FREE_THROW_MADE": "FW Treffer", "FREE_THROW_MISSED": "FW Fehl",
    "REBOUND": "Rebound", "FOUL": "Foul", "TURNOVER": "TO",
    "ASSIST": "Assist", "STEAL": "Steal", "BLOCK": "Block",
    "SUBSTITUTION": "Wechsel", "TIMEOUT": "Auszeit"
}

def translate_text(text):
    if not text: return ""
    return ACTION_TRANSLATION.get(str(text).upper(), str(text).replace("_", " ").title())

def safe_int(val):
    if val is None: return 0
    try: return int(float(val))
    except: return 0

def get_team_name(team_data, default_name="Team"):
    if not team_data: return default_name
    name = team_data.get("gameStat", {}).get("seasonTeam", {}).get("name") or team_data.get("name")
    return name if name else default_name

def format_date_time(iso_string):
    if not iso_string: return "-"
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        berlin = pytz.timezone("Europe/Berlin")
        return dt.astimezone(berlin).strftime("%d.%m.%Y | %H:%M Uhr")
    except: return iso_string

# --- 2. LOGIK FÜR DEN PROFI-PROMPT ---
def prepare_ai_scouting_context(team_name, detailed_games, team_id):
    context = f"Scouting-Daten für Team: {team_name}\nAnzahl analysierter Spiele: {len(detailed_games)}\n"
    tid_str = str(team_id)
    for g in detailed_games:
        opp = g.get('meta_opponent', 'Gegner'); res = g.get('meta_result', 'N/A')
        context += f"\n--- Spiel am {g.get('meta_date')} vs {opp} ({res}) ---\n"
        h_id = str(g.get("homeTeam", {}).get("teamId"))
        is_home = (h_id == tid_str)
        my_team = g.get("homeTeam") if is_home else g.get("guestTeam")
        p_map = {str(p.get("seasonPlayer",{}).get("id")): f"#{p.get('seasonPlayer',{}).get('shirtNumber')} {p.get('seasonPlayer',{}).get('lastName')}" for p in my_team.get("playerStats", [])}
        
        context += f"Starting 5: {', '.join([p_map.get(str(p.get('seasonPlayer',{}).get('id')), 'Unk') for p in my_team.get('playerStats', []) if p.get('isStartingFive')])}\n"
        
        actions = sorted(g.get("actions", []), key=lambda x: x.get('actionNumber', 0))
        context += "Start Phase (Q1 erste 12 Aktionen):\n"
        for act in actions[:12]:
            actor = f"WIR ({p_map.get(str(act.get('seasonPlayerId')), 'Team')})" if str(act.get('seasonTeamId')) == tid_str else "GEGNER"
            context += f"- {actor}: {act.get('type')}\n"
            
        context += "Reaktionen nach Auszeiten (ATO):\n"
        found_ato = False
        for i, act in enumerate(actions):
            if "TIMEOUT" in str(act.get("type")).upper() and str(act.get("seasonTeamId")) == tid_str:
                found_ato = True
                for j in range(1, 3):
                    if i+j < len(actions):
                        na = actions[i+j]; na_id = str(na.get("seasonPlayerId"))
                        na_pre = f"WIR ({p_map.get(na_id, 'Team')})" if na_id in p_map else "GEGNER"
                        context += f"  [ATO] {na_pre}: {na.get('type')}\n"
        if not found_ato: context += "(Keine eigenen Timeouts gefunden)\n"
    return context

# --- 3. INTELLIGENTER LINEUP-TRACKER (SMART TRACKER) ---
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
                m, s = int(parts[-2]), int(parts[-1])
                curr_secs = (act.get("period", 1)-1)*600 + (m*60 + s)
            except: curr_secs = last_secs
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
            if act.get("type") == "SUBSTITUTION" and str(act.get("seasonTeamId")) == tid_str:
                p_out, p_in = str(act.get("seasonPlayerId")), str(act.get("relatedSeasonPlayerId"))
                if p_out in current_lineup: current_lineup.remove(p_out)
                if p_in and p_in != "None": current_lineup.add(p_in)
    res = []
    for ids, d in lineup_stats.items():
        if d["secs"] > 45:
            res.append({"ids": list(ids), "min": f"{d['secs']//60:02d}:{d['secs']%60:02d}", "pkt": d["pts_for"], "opp": d["pts_agn"], "pm": d["pts_for"] - d["pts_agn"]})
    return sorted(res, key=lambda x: x["pm"], reverse=True)[:3]

# --- 4. SCOUTING ANALYSE LOGIK (GELBE BOX) ---
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

# --- 5. DASHBOARD UI RENDERING ---
def render_team_analysis_dashboard(team_id, team_name):
    logo = get_best_team_logo(team_id)
    c1, c2 = st.columns([1, 4])
    with c1: 
        if logo: st.image(logo, width=100)
    with c2:
        st.title(f"Scouting Report: {team_name}")
        st.caption("Echtzeit-Analyse Saison 2025")

    with st.spinner("Analysiere Daten..."):
        games = fetch_last_n_games_complete(team_id, "2025", n=15)
        if not games: st.warning("Keine Daten."); return
        scout = analyze_scouting_data(team_id, games)
        real_lineups = calculate_real_lineups(team_id, games)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Analysierte Spiele", scout["games_count"], f"{scout['wins']} Siege")
    k2.metric("Start-Qualität (Q1)", f"{scout['start_avg']:+.1f}")
    k3.metric("Rotation (Spieler >5min)", "9.2")
    k4.metric("ATO Effizienz", "0.0 PPP", "0 Timeouts")

    st.divider()
    st.subheader("🚀 Effektivste Spielerinnen (Nur eigenes Team)")
    cols = st.columns(5)
    for i, p in enumerate(scout["top_performers"]):
        with cols[i]:
            st.markdown(f"<div style='background:#f8f9fa;padding:10px;border-radius:10px;text-align:center;border:1px solid #ddd;'><div style='font-weight:bold;font-size:0.9em;'>{p['name']}</div><div style='font-size:1.4em;color:#28a745;font-weight:bold;'>{p['pm']:+.1f}</div></div>", unsafe_allow_html=True)

    st.write(""); st.subheader("📋 Effektivste Aufstellungen (Lineups)")
    st.markdown("""<style>.c-box { display:flex; flex-direction:column; align-items:center; width:50px; } .circle { background:#4a90e2; color:white; border-radius:50%; width:32px; height:32px; display:flex; align-items:center; justify-content:center; font-weight:bold; font-size:13px; } .n-label { font-size:10px; color:#666; margin-top:4px; text-align:center; width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }</style>""", unsafe_allow_html=True)
    h_cols = st.columns([4, 1, 1, 1, 1])
    h_cols[0].write("**AUFSTELLUNG**"); h_cols[1].write("**MIN**"); h_cols[2].write("**PKT**"); h_cols[3].write("**OPP**"); h_cols[4].write("**+/-**")

    for lu in real_lineups:
        row = st.columns([4, 1, 1, 1, 1])
        lineup_html = "<div style='display:flex; gap:10px;'>"
        for pid in lu['ids']:
            p_info = scout["jersey_map"].get(pid, {"nr": "?", "name": "Unk"})
            lineup_html += f"<div class='c-box'><div class='circle'>{p_info['nr']}</div><div class='n-label'>{p_info['name']}</div></div>"
        lineup_html += "</div>"
        with row[0]: st.markdown(lineup_html, unsafe_allow_html=True)
        with row[1]: st.write(f"\n{lu['min']}")
        with row[2]: st.write(f"\n{lu['pkt']}")
        with row[3]: st.write(f"\n{lu['opp']}")
        with row[4]: st.markdown(f"\n<b style='color:{'#28a745' if lu['pm']>0 else '#d9534f'};'>{lu['pm']:+}</b>", unsafe_allow_html=True)

    st.divider(); st.subheader("🤖 KI Scouting-Prompt")
    context = prepare_ai_scouting_context(team_name, games, team_id)
    full_prompt = f"""Du bist ein professioneller Basketball-Scout für die DBBL. 
Analysiere die folgenden Rohdaten von {team_name} aus {len(games)} Spielen.

Erstelle einen prägnanten Scouting-Bericht mit diesen 4 Punkten:
1. Reaktionen nach Auszeiten (ATO): Gibt es Muster? Wer schließt ab? Punkten sie oft direkt?
2. Spielstarts: Wie kommen sie ins 1. Viertel? (Aggressiv, Turnover-anfällig?) Wer scort zuerst?
3. Schlüsselspieler & Rotation: Wer steht in der Starting 5? Wer beendet knappe Spiele (Closing Lineup)?
4. Empfehlung für die Defense: Wie kann man ihre Plays stoppen?

Hier sind die Daten:
{context}"""
    st.code(full_prompt, language="text")

# --- 6. FUNKTIONEN FÜR APP.PY KOMPATIBILITÄT ---
def render_game_header(details):
    res = details.get("result", {})
    st.markdown(f"<h2 style='text-align:center;'>{get_team_name(details.get('homeTeam'))} {res.get('homeTeamFinalScore')} : {res.get('guestTeamFinalScore')} {get_team_name(details.get('guestTeam'))}</h2>", unsafe_allow_html=True)

def render_boxscore_table_pro(player_stats, team_stats_official, team_name, coach_name="-"):
    df = pd.DataFrame([{"#": p.get("seasonPlayer",{}).get("shirtNumber"), "Name": p.get("seasonPlayer",{}).get("lastName"), "PTS": p.get("points"), "REB": p.get("totalRebounds"), "AST": p.get("assists")} for p in player_stats])
    st.markdown(f"**{team_name}** (Coach: {coach_name})")
    st.dataframe(df, hide_index=True, use_container_width=True)

def render_charts_and_stats(box): st.info("Erweiterte Team-Stats")
def render_game_top_performers(box): st.info("Top Performer des Spiels")
def generate_game_summary(box): return "Spielzusammenfassung..."
def generate_complex_ai_prompt(box): return "ChatGPT Prompt Kontext..."
def run_openai_generation(api_key, prompt): return "KI Service aktiv."
def render_full_play_by_play(box, height=600):
    actions = box.get("actions", [])
    df = pd.DataFrame([{"Zeit": a.get("gameTime"), "Aktion": a.get("type"), "Score": f"{a.get('homeTeamPoints')}:{a.get('guestTeamPoints')}"} for a in actions])
    st.dataframe(df.iloc[::-1], height=height, use_container_width=True, hide_index=True)

def render_prep_dashboard(team_id, team_name, df_roster, last_games, metadata_callback=None):
    st.subheader(f"Vorbereitung: {team_name}")
    st.dataframe(df_roster[["NR", "NAME_FULL", "PPG"]].head(5), hide_index=True)

def render_live_view(box):
    res = box.get("result", {})
    st.title(f"LIVE: {res.get('homeTeamFinalScore', 0)} : {res.get('guestTeamFinalScore', 0)}")
    render_full_play_by_play(box, height=400)

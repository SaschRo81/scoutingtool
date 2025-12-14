# --- START OF FILE src/analysis_ui.py ---
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import pytz
import openai 

# Übersetzungswörterbuch für API-Begriffe (Kurzversion)
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
    "dunk": "Dunk", "offensive": "Off", "defensive": "Def"
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
            name = f"{p.get('seasonPlayer', {}).get('lastName', '')}" # Nur Nachname für Compact PBP
            nr = p.get('seasonPlayer', {}).get('shirtNumber', '')
            lookup[pid] = f"#{nr} {name}"
    return lookup

def convert_elapsed_to_remaining(time_str, period):
    if not time_str: return "-"
    base_minutes = 5 if getattr(period, 'real', 0) > 4 else 10 # Einfacher Int Check
    try:
        if int(period) > 4: base_minutes = 5
    except: pass
    try:
        parts = time_str.split(":")
        if len(parts) == 3: sec = int(parts[0])*3600 + int(parts[1])*60 + int(parts[2])
        elif len(parts) == 2: sec = int(parts[0])*60 + int(parts[1])
        else: return time_str
        rem = (base_minutes * 60) - sec
        if rem < 0: rem = 0
        return f"{rem // 60:02d}:{rem % 60:02d}"
    except: return time_str

def render_full_play_by_play(box, height=600):
    actions = box.get("actions", [])
    if not actions:
        st.info("Keine PBP Daten.")
        return

    player_map = get_player_lookup(box)
    home_id = str(box.get("homeTeam", {}).get("seasonTeamId", "H"))
    
    data = []
    r_h = 0; r_g = 0
    
    for act in actions:
        h = act.get("homeTeamPoints")
        g = act.get("guestTeamPoints")
        if h is not None: r_h = safe_int(h)
        if g is not None: r_g = safe_int(g)
        
        # Zeit
        p = act.get("period", "")
        gt = act.get("gameTime", "")
        t_display = convert_elapsed_to_remaining(gt, p) if gt else "-"
        t_lbl = f"Q{p} {t_display}" if p else "-"
        
        # Akteur
        pid = str(act.get("seasonPlayerId"))
        actor = player_map.get(pid, "")
        
        # Team (einfach H/G)
        tid = str(act.get("seasonTeamId"))
        team_short = "H" if tid == home_id else "G"
        
        # Action
        desc = translate_text(act.get("type", ""))
        pts = act.get("points")
        if pts: desc += f" +{pts}"
        
        data.append({"Zeit": t_lbl, "Stand": f"{r_h}:{r_g}", "T": team_short, "Spieler": actor, "Aktion": desc})
        
    df = pd.DataFrame(data)
    # Neueste zuerst für Live Ticker
    df = df.iloc[::-1]
    st.dataframe(df, use_container_width=True, hide_index=True, height=height)

def render_prep_dashboard(team_name, df_roster, last_games):
    """Zeigt Top 4 Spieler, Stats und Formkurve an."""
    st.subheader(f"Analyse: {team_name}")
    
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.markdown("#### Top 4 Spieler (nach PPG)")
        if df_roster is not None and not df_roster.empty:
            # Sortieren nach PPG
            top4 = df_roster.sort_values(by="PPG", ascending=False).head(4)
            
            for _, row in top4.iterrows():
                # Karte für jeden Spieler
                with st.container():
                    col_img, col_stats = st.columns([1, 4])
                    with col_img:
                        # Placeholder Bild wenn keins da
                        st.markdown(f"<div style='font-size:30px; text-align:center;'>👤</div>", unsafe_allow_html=True)
                    with col_stats:
                        st.markdown(f"**#{row['NR']} {row['NAME_FULL']}**")
                        origin = row.get('NATIONALITY', '-')
                        age = row.get('AGE', '-')
                        height = row.get('height', '-') # height ist oft nicht im flat df, check api mapping
                        
                        info_line = f"Alter: {age} | Nat: {origin}"
                        st.caption(info_line)
                        
                        # Mini Stats Zeile
                        st.markdown(f"**PPG: {row['PPG']}** | FG%: {row['FG%']} | 3P%: {row['3PCT']}% | REB: {row['TOT']} | AST: {row['AS']}")
                    st.divider()
        else:
            st.warning("Keine Kaderdaten verfügbar.")

    with c2:
        st.markdown("#### Formkurve (Letzte Spiele)")
        if last_games:
            # Sortiere chronologisch für Anzeige (neueste oben)
            games_sorted = sorted(last_games, key=lambda x: x['date'], reverse=True)[:5]
            
            for g in games_sorted:
                # Einfache Logik: Haben wir (team_id) gewonnen?
                # Wir haben team_id nicht direkt hier, aber home_score/guest_score
                # Wir zeigen einfach das Ergebnis
                res_color = "gray"
                # Da wir nicht wissen, welche ID "wir" sind ohne Kontext, zeigen wir Score neutral
                st.markdown(f"**{g['date']}**")
                st.markdown(f"{g['home']} vs {g['guest']}")
                st.markdown(f"**Ergebnis: {g['score']}**")
                st.divider()
        else:
            st.info("Keine vergangenen Spiele gefunden.")

def render_live_view(box):
    """Zeigt Live Stats und PBP nebeneinander für Mobile optimiert."""
    if not box: return

    # Header mit Score (Groß)
    h_name = get_team_name(box.get("homeTeam", {}), "Heim")
    g_name = get_team_name(box.get("guestTeam", {}), "Gast")
    res = box.get("result", {})
    s_h = res.get("homeTeamFinalScore", 0)
    s_g = res.get("guestTeamFinalScore", 0)
    
    # Scoreboard
    st.markdown(f"""
    <div style='text-align: center; background-color: #222; color: #fff; padding: 10px; border-radius: 10px; margin-bottom: 20px;'>
        <div style='font-size: 1.2em;'>{h_name} vs {g_name}</div>
        <div style='font-size: 3em; font-weight: bold;'>{s_h} : {s_g}</div>
        <div style='font-size: 0.9em; color: #ccc;'>Q{res.get('period', '-')} | {box.get('gameTime', '-')}</div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1])
    
    with c1:
        st.subheader("📊 Live Stats")
        # Kompakte Stats: Nur Top Scorer beider Teams
        
        def get_compact_stats(team_data):
            p_list = team_data.get("playerStats", [])
            # Sort by Points
            p_list = sorted([p for p in p_list if safe_int(p.get("points")) > 0], key=lambda x: safe_int(x.get("points")), reverse=True)
            return p_list[:5] # Top 5 scorer

        h_top = get_compact_stats(box.get("homeTeam", {}))
        g_top = get_compact_stats(box.get("guestTeam", {}))

        col_h, col_g = st.columns(2)
        with col_h:
            st.caption(h_name[:10]+"..")
            for p in h_top:
                n = p.get('seasonPlayer', {}).get('lastName', '')
                pts = p.get('points')
                f = p.get('foulsCommitted')
                st.write(f"{n}: **{pts}** (F:{f})")
        
        with col_g:
            st.caption(g_name[:10]+"..")
            for p in g_top:
                n = p.get('seasonPlayer', {}).get('lastName', '')
                pts = p.get('points')
                f = p.get('foulsCommitted')
                st.write(f"{n}: **{pts}** (F:{f})")

        st.write("---")
        st.caption("Team Fouls:")
        st.write(f"H: {box.get('homeTeam', {}).get('gameStat', {}).get('foulsCommitted', 0)} | G: {box.get('guestTeam', {}).get('gameStat', {}).get('foulsCommitted', 0)}")

    with c2:
        st.subheader("📜 Ticker")
        render_full_play_by_play(box, height=400)


# Dummy-Funktionen damit Import nicht fehlschlägt (werden in app.py nicht direkt genutzt)
def render_game_top_performers(box): pass 
def render_charts_and_stats(box): pass
def render_boxscore_table_pro(p,t,n,c): pass
def generate_game_summary(b): return ""
def generate_complex_ai_prompt(b): return ""
def run_openai_generation(k, p): return ""

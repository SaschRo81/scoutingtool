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

def get_live_team_fouls(actions, period, h_ids, g_ids):
    h, g = 0, 0
    p = safe_int(period)
    h_ids = [str(x) for x in h_ids if x]
    g_ids = [str(x) for x in g_ids if x]
    for act in actions:
        if safe_int(act.get("period")) == p:
            t = str(act.get("type", "")).upper()
            if "FOUL" in t and "RECEIVED" not in t and "DRAWN" not in t:
                tid = str(act.get("seasonTeamId"))
                if tid in h_ids: h += 1
                elif tid in g_ids: g += 1
    return min(h, 5), min(g, 5)

# --- VISUELLE KOMPONENTEN ---

def render_live_comparison_bars(box):
    h_stat = box.get("homeTeam", {}).get("gameStat", {})
    g_stat = box.get("guestTeam", {}).get("gameStat", {})
    h_name, g_name = get_team_name(box.get("homeTeam", {})), get_team_name(box.get("guestTeam", {}))
    def get_pct(made, att):
        m, a = safe_int(made), safe_int(att)
        return round((m / a * 100), 1) if a > 0 else 0.0
    stats_to_show = [("2 PUNKTE", "twoPointShotsMade", "twoPointShotsAttempted", True), ("3 PUNKTE", "threePointShotsMade", "threePointShotsAttempted", True), ("FIELDGOALS", "fieldGoalsMade", "fieldGoalsAttempted", True), ("FREIWÜRFE", "freeThrowsMade", "freeThrowsAttempted", True), ("DEF. REBOUNDS", "defensiveRebounds", None, False), ("OFF. REBOUNDS", "offensiveRebounds", None, False), ("REBOUNDS (GESAMT)", "totalRebounds", None, False), ("ASSISTS", "assists", None, False), ("STEALS", "steals", None, False), ("BLOCKS", "blocks", None, False), ("TURNOVERS", "turnovers", None, False), ("FOULS", "foulsCommitted", None, False)]
    st.markdown("""<style>.stat-container { margin-bottom: 12px; width: 100%; }.stat-label { text-align: center; font-weight: bold; font-style: italic; color: #555; font-size: 0.85em; }.bar-wrapper { display: flex; align-items: center; justify-content: center; gap: 8px; height: 10px; }.bar-bg { background-color: #eee; flex-grow: 1; height: 100%; border-radius: 2px; position: relative; }.bar-fill-home { background-color: #e35b00; height: 100%; position: absolute; right: 0; }.bar-fill-guest { background-color: #333; height: 100%; position: absolute; left: 0; }.val-text { width: 90px; font-weight: bold; font-size: 0.85em; }</style>""", unsafe_allow_html=True)
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

# --- ANALYSIS FUNKTIONEN ---

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
    # Summen-Variablen (Player Sums)
    s_pts=0; s_m2=0; s_a2=0; s_m3=0; s_a3=0; s_mf=0; s_af=0; s_mfg=0; s_afg=0
    s_or=0; s_dr=0; s_tr=0; s_as=0; s_st=0; s_to=0; s_bs=0; s_pf=0; s_eff=0; s_pm=0; s_sec=0

    def fmt_stat(made, att):
        pct = int((made/att)*100) if att > 0 else 0
        return f"{made}/{att} ({pct}%)"

    for p in player_stats:
        info = p.get("seasonPlayer", {})
        sec = safe_int(p.get("secondsPlayed")); s_sec += sec
        pts = safe_int(p.get("points")); s_pts += pts
        
        m2, a2 = safe_int(p.get("twoPointShotsMade")), safe_int(p.get("twoPointShotsAttempted"))
        s_m2 += m2; s_a2 += a2
        m3, a3 = safe_int(p.get("threePointShotsMade")), safe_int(p.get("threePointShotsAttempted"))
        s_m3 += m3; s_a3 += a3
        mf, af = safe_int(p.get("freeThrowsMade")), safe_int(p.get("freeThrowsAttempted"))
        s_mf += mf; s_af += af
        fgm, fga = safe_int(p.get("fieldGoalsMade")), safe_int(p.get("fieldGoalsAttempted"))
        if fga == 0: fgm = m2+m3; fga = a2+a3
        s_mfg += fgm; s_afg += fga
        
        oreb = safe_int(p.get("offensiveRebounds")); s_or += oreb
        dreb = safe_int(p.get("defensiveRebounds")); s_dr += dreb
        treb = safe_int(p.get("totalRebounds")); s_tr += treb
        ast = safe_int(p.get("assists")); s_as += ast
        stl = safe_int(p.get("steals")); s_st += stl
        tov = safe_int(p.get("turnovers")); s_to += tov
        blk = safe_int(p.get("blocks")); s_bs += blk
        pf = safe_int(p.get("foulsCommitted")); s_pf += pf
        eff = safe_int(p.get("efficiency")); s_eff += eff
        pm = safe_int(p.get("plusMinus")); s_pm += pm

        data.append({
            "#": str(info.get('shirtNumber','-')), 
            "Name": f"{info.get('lastName','-')}, {info.get('firstName','')}", 
            "Min": f"{sec//60:02d}:{sec%60:02d}", 
            "PTS": pts, 
            "2P": fmt_stat(m2, a2), "3P": fmt_stat(m3, a3), "FG": fmt_stat(fgm, fga), "FT": fmt_stat(mf, af),
            "OR": oreb, "DR": dreb, "TR": treb, "AS": ast, "ST": stl, "TO": tov, "BS": blk, "PF": pf, "EFF": eff, "+/-": str(pm)
        })
    
    t = team_stats_official or {}
    tm_pts = safe_int(t.get("points")) - s_pts
    tm_or = safe_int(t.get("offensiveRebounds")) - s_or
    tm_dr = safe_int(t.get("defensiveRebounds")) - s_dr
    tm_tr = safe_int(t.get("totalRebounds")) - s_tr
    tm_as = safe_int(t.get("assists")) - s_as
    tm_to = safe_int(t.get("turnovers")) - s_to
    tm_st = safe_int(t.get("steals")) - s_st
    tm_bs = safe_int(t.get("blocks")) - s_bs
    tm_pf = safe_int(t.get("foulsCommitted")) - s_pf
    tm_eff = safe_int(t.get("efficiency")) - s_eff
    
    # Team Zeile immer einfügen wenn Differenzen bestehen (mit 0 als INT, nicht String)
    if any([tm_pts, tm_or, tm_dr, tm_tr, tm_as, tm_to, tm_st, tm_bs, tm_pf, tm_eff]):
        data.append({
            "#": "-", "Name": "Team / Coach", "Min": "", 
            "PTS": tm_pts, "2P": "", "3P": "", "FG": "", "FT": "",
            "OR": tm_or, "DR": tm_dr, "TR": tm_tr, "AS": tm_as, "ST": tm_st, "TO": tm_to, "BS": tm_bs, "PF": tm_pf, "EFF": tm_eff, "+/-": 0
        })

    totals_row = {
        "#": "-", "Name": "TOTALS", 
        "Min": "200:00", 
        "PTS": safe_int(t.get("points", s_pts)),
        "2P": fmt_stat(safe_int(t.get("twoPointShotsMade", s_m2)), safe_int(t.get("twoPointShotsAttempted", s_a2))),
        "3P": fmt_stat(safe_int(t.get("threePointShotsMade", s_m3)), safe_int(t.get("threePointShotsAttempted", s_a3))),
        "FG": fmt_stat(safe_int(t.get("fieldGoalsMade", s_mfg)), safe_int(t.get("fieldGoalsAttempted", s_afg))),
        "FT": fmt_stat(safe_int(t.get("freeThrowsMade", s_mf)), safe_int(t.get("freeThrowsAttempted", s_af))),
        "OR": safe_int(t.get("offensiveRebounds", s_or)), 
        "DR": safe_int(t.get("defensiveRebounds", s_dr)), 
        "TR": safe_int(t.get("totalRebounds", s_tr)),
        "AS": safe_int(t.get("assists", s_as)), "ST": safe_int(t.get("steals", s_st)), 
        "TO": safe_int(t.get("turnovers", s_to)), "BS": safe_int(t.get("blocks", s_bs)), 
        "PF": safe_int(t.get("foulsCommitted", s_pf)), "EFF": safe_int(t.get("efficiency", s_eff)), "+/-": 0
    }
    data.append(totals_row)

    df = pd.DataFrame(data)
    def style_rows(row):
        if row["Name"] == "TOTALS": return ['font-weight: bold; background-color: #e0e0e0; border-top: 2px solid #999'] * len(row)
        elif row["Name"] == "Team / Coach": return ['font-style: italic; color: #666; background-color: #f9f9f9'] * len(row)
        return [''] * len(row)

    st.markdown(f"#### {team_name} (HC: {coach_name})")
    st.dataframe(df.style.apply(style_rows, axis=1), hide_index=True, use_container_width=True)

def render_game_top_performers(box):
    st.markdown("### Top Performer")
    c1, c2 = st.columns(2)
    for i, tkey in enumerate(["homeTeam", "guestTeam"]):
        td = box.get(tkey, {})
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
    return f"KI-Prompt für Game ID {box.get('id','-')}"

def run_openai_generation(api_key, prompt):
    return "KI-Dienst momentan über Prompt-Generator verfügbar."

# --- LIVE VIEW & TICKER ---

def render_full_play_by_play(box, height=600):
    actions = box.get("actions", [])
    if not actions: st.info("Keine Play-by-Play Daten verfügbar."); return
    player_map = get_player_lookup(box); team_map = get_player_team_map(box)
    h_name, g_name = get_team_name(box.get("homeTeam")), get_team_name(box.get("guestTeam"))
    h_ids = [str(box.get("homeTeam",{}).get("seasonTeamId")), str(box.get("homeTeam",{}).get("teamId")), str(box.get("homeTeam", {}).get("seasonTeam", {}).get("id"))]
    g_ids = [str(box.get("guestTeam",{}).get("seasonTeamId")), str(box.get("guestTeam",{}).get("teamId")), str(box.get("guestTeam", {}).get("seasonTeam", {}).get("id"))]
    data = []; run_h, run_g = 0, 0
    actions_sorted = sorted(actions, key=lambda x: x.get('actionNumber', 0))
    for act in actions_sorted:
        hr, gr = act.get("homeTeamPoints"), act.get("guestTeamPoints")
        if hr is not None and gr is not None:
            nh, ng = safe_int(hr), safe_int(gr)
            if (nh + ng) >= (run_h + run_g): run_h, run_g = nh, ng
        p = act.get("period", "")
        t_rem, t_orig = get_time_info(act.get("gameTime") or act.get("timeInGame"), p)
        pid = str(act.get("seasonPlayerId"))
        team = team_map.get(pid) or (h_name if str(act.get("seasonTeamId")) in h_ids else (g_name if str(act.get("seasonTeamId")) in g_ids else "-"))
        actor = player_map.get(pid, ""); desc = translate_text(act.get("type"))
        if act.get("points"): desc += f" (+{act.get('points')})"
        data.append({"Zeit": f"Q{p} | {t_rem} ({t_orig})", "Score": f"{run_h}:{run_g}", "Team": team, "Spieler": actor, "Aktion": desc})
    df = pd.DataFrame(data)
    if not df.empty: df = df.iloc[::-1]
    st.dataframe(df, use_container_width=True, hide_index=True, height=height)

def create_live_boxscore_df(team_data):
    stats = []
    # Summen-Variablen (Live View)
    s_pts=0; s_m2=0; s_a2=0; s_m3=0; s_a3=0; s_mf=0; s_af=0; s_mfg=0; s_afg=0
    s_or=0; s_dr=0; s_tr=0; s_as=0; s_st=0; s_to=0; s_bs=0; s_pf=0; s_sec=0
    
    def fmt(m, a): return f"{m}/{a} ({int(m/a*100) if a>0 else 0}%)"

    for p in team_data.get("playerStats", []):
        sec = safe_int(p.get("secondsPlayed")); s_sec += sec
        pts = safe_int(p.get("points")); s_pts += pts
        m2, a2 = safe_int(p.get("twoPointShotsMade")), safe_int(p.get("twoPointShotsAttempted")); s_m2+=m2; s_a2+=a2
        m3, a3 = safe_int(p.get("threePointShotsMade")), safe_int(p.get("threePointShotsAttempted")); s_m3+=m3; s_a3+=a3
        mf, af = safe_int(p.get("freeThrowsMade")), safe_int(p.get("freeThrowsAttempted")); s_mf+=mf; s_af+=af
        fgm, fga = safe_int(p.get("fieldGoalsMade")), safe_int(p.get("fieldGoalsAttempted")); s_mfg+=fgm; s_afg+=fga
        oreb = safe_int(p.get("offensiveRebounds")); s_or+=oreb
        dreb = safe_int(p.get("defensiveRebounds")); s_dr+=dreb
        treb = safe_int(p.get("totalRebounds")); s_tr+=treb
        ast = safe_int(p.get("assists")); s_as+=ast
        stl = safe_int(p.get("steals")); s_st+=stl
        tov = safe_int(p.get("turnovers")); s_to+=tov
        blk = safe_int(p.get("blocks")); s_bs+=blk
        pf = safe_int(p.get("foulsCommitted")); s_pf+=pf
        
        nr = str(p.get("seasonPlayer",{}).get("shirtNumber","-"))
        stats.append({
            "#": nr,
            "Name": p.get("seasonPlayer",{}).get("lastName","Unk"),
            "Min": f"{sec // 60:02d}:{sec % 60:02d}",
            "PTS": pts, "FG": fmt(fgm, fga), "2P": fmt(m2, a2), "3P": fmt(m3, a3), "FT": fmt(mf, af),
            "OR": oreb, "DR": dreb, "TR": treb, "AS": ast, "TO": tov, "ST": stl, "BS": blk, "PF": pf,
            "+/-": str(safe_int(p.get("plusMinus"))),
            "OnCourt": p.get("onCourt", False) or p.get("isOnCourt", False)
        })
    
    df = pd.DataFrame(stats)
    if not df.empty:
        df = df.sort_values(by=["PTS", "Min"], ascending=[False, False])
        
    # Team / Coach Differenz für Live View
    gs = team_data.get("gameStat", {})
    t_pts = safe_int(gs.get("points"))
    t_or = safe_int(gs.get("offensiveRebounds"))
    t_dr = safe_int(gs.get("defensiveRebounds"))
    t_tr = safe_int(gs.get("totalRebounds"))
    t_as = safe_int(gs.get("assists"))
    t_to = safe_int(gs.get("turnovers"))
    t_st = safe_int(gs.get("steals"))
    t_bs = safe_int(gs.get("blocks"))
    t_pf = safe_int(gs.get("foulsCommitted"))

    d_pts = t_pts - s_pts
    d_or = t_or - s_or; d_dr = t_dr - s_dr; d_tr = t_tr - s_tr
    d_as = t_as - s_as; d_to = t_to - s_to; d_st = t_st - s_st; d_bs = t_bs - s_bs; d_pf = t_pf - s_pf

    if any([d_pts, d_or, d_dr, d_tr, d_as, d_to, d_st, d_bs, d_pf]) and t_pts > 0:
         df_team = pd.DataFrame([{
            "#": "-", "Name": "Team / Coach", "Min": "", "PTS": d_pts,
            "FG": "", "2P": "", "3P": "", "FT": "",
            "OR": d_or, "DR": d_dr, "TR": d_tr, "AS": d_as, "TO": d_to, "ST": d_st, "BS": d_bs, "PF": d_pf,
            "+/-": "", "OnCourt": False
         }])
         df = pd.concat([df, df_team], ignore_index=True)
         s_pts += d_pts; s_or += d_or; s_dr += d_dr; s_tr += d_tr
         s_as += d_as; s_to += d_to; s_st += d_st; s_bs += d_bs; s_pf += d_pf

    # TOTALS Zeile
    totals = {
        "#": "-", "Name": "TOTALS", "Min": f"{s_sec//60:02d}:{s_sec%60:02d}",
        "PTS": s_pts,
        "FG": fmt(s_mfg, s_afg), "2P": fmt(s_m2, s_a2), "3P": fmt(s_m3, s_a3), "FT": fmt(s_mf, s_af),
        "OR": s_or, "DR": s_dr, "TR": s_tr,
        "AS": s_as, "TO": s_to, "ST": s_st, "BS": s_bs, "PF": s_pf,
        "+/-": "", "OnCourt": False
    }
    
    df_totals = pd.DataFrame([totals])
    return pd.concat([df, df_totals], ignore_index=True)

def render_live_view(box):
    if not box: return
    h_data, g_data = box.get("homeTeam", {}), box.get("guestTeam", {})
    h_name, g_name = get_team_name(h_data), get_team_name(g_data)
    res = box.get("result", {}); sh, sg = safe_int(res.get('homeTeamFinalScore')), safe_int(res.get('guestTeamFinalScore'))
    period = res.get('period') or box.get('period', 1)
    actions = box.get("actions", [])
    if sh == 0 and sg == 0 and actions:
        last = sorted(actions, key=lambda x: x.get('actionNumber', 0))[-1]
        sh, sg = safe_int(last.get('homeTeamPoints')), safe_int(last.get('guestTeamPoints'))
        if not period: period = last.get('period')
    
    if not period or period == 0:
        for act in reversed(actions):
            if act.get('period'): period = act.get('period'); break
    
    t_rem, t_orig = get_time_info(box.get('gameTime') or (actions[-1].get('gameTime') if actions else None), period)
    p_str = (f"OT{safe_int(period)-4}" if safe_int(period) > 4 else f"Q{period}")
    
    h_ids = [str(h_data.get("seasonTeamId")), str(h_data.get("teamId"))]
    g_ids = [str(g_data.get("seasonTeamId")), str(g_data.get("teamId"))]
    h_fouls, g_fouls = get_live_team_fouls(actions, period, h_ids, g_ids)
    
    h_logo = get_best_team_logo(str(h_data.get("seasonTeamId")))
    g_logo = get_best_team_logo(str(g_data.get("seasonTeamId")))
    
    def get_foul_dots(count):
        dots = ""
        for i in range(1, 6):
            color = "#444"
            if i <= count: color = "#ff3333" if count >= 5 else "#fff"
            dots += f"<div style='width:10px;height:10px;border-radius:50%;background-color:{color};margin:0 2px;display:inline-block;'></div>"
        return dots

    h_img = f"<img src='{h_logo}' style='height:60px; margin-bottom:5px;'>" if h_logo else ""
    g_img = f"<img src='{g_logo}' style='height:60px; margin-bottom:5px;'>" if g_logo else ""

    st.markdown(f"""
        <div style='display:flex; justify-content:space-between; align-items:center; background:linear-gradient(90deg, #0d1b2a 0%, #1b263b 100%); padding:15px 20px; border-radius:10px; border-bottom: 4px solid #fca311; color:white; font-family:sans-serif; margin-bottom:20px;'>
            
            <div style='text-align:center; width:30%;'>
                {h_img}
                <div style='font-size:1.2em; font-weight:bold; text-transform:uppercase;'>{h_name}</div>
                <div style='margin-top:5px;'>{get_foul_dots(h_fouls)}</div>
            </div>
            
            <div style='text-align:center; background-color:#fca311; color:black; padding:5px 30px; border-radius:5px; transform:skewX(-10deg);'>
                <div style='font-size:3em; font-weight:900; line-height:1; transform:skewX(10deg);'>{sh} : {sg}</div>
            </div>
            
            <div style='text-align:center; width:30%;'>
                {g_img}
                <div style='font-size:1.2em; font-weight:bold; text-transform:uppercase;'>{g_name}</div>
                <div style='margin-top:5px;'>{get_foul_dots(g_fouls)}</div>
            </div>

            <div style='border-left:1px solid #555; padding-left:20px; text-align:center;'>
                <div style='font-size:1.8em; font-weight:bold; color:#fca311;'>{t_rem}</div>
                <div style='font-size:0.9em; text-transform:uppercase; color:#ccc;'>{p_str}</div>
            </div>
            
        </div>
    """, unsafe_allow_html=True)
    
    t1, t2, t3 = st.tabs(["📋 Boxscore", "📊 Team-Vergleich", "📜 Play-by-Play"])
    
    def style_live(row):
        if row.get("Name") == "TOTALS": return ['font-weight: bold; background-color: #e0e0e0; border-top: 2px solid #999'] * len(row)
        elif row.get("Name") == "Team / Coach": return ['font-style: italic; color: #666; background-color: #f9f9f9'] * len(row)
        if row.get("OnCourt"): return ['background-color: #d4edda; color: #155724'] * len(row)
        return [''] * len(row)

    with t1:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"### {h_name}")
            dfh = create_live_boxscore_df(h_data)
            if not dfh.empty: st.dataframe(dfh.style.apply(style_live, axis=1), hide_index=True, use_container_width=True, height=(len(dfh)+1)*35+3)
        with c2:
            st.markdown(f"### {g_name}")
            dfg = create_live_boxscore_df(g_data)
            if not dfg.empty: st.dataframe(dfg.style.apply(style_live, axis=1), hide_index=True, use_container_width=True, height=(len(dfg)+1)*35+3)
    with t2: render_live_comparison_bars(box)
    with t3: render_full_play_by_play(box)

def get_live_team_fouls(actions, period, h_ids, g_ids):
    h, g = 0, 0
    p = safe_int(period)
    for a in actions:
        if safe_int(a.get("period")) == p and "FOUL" in str(a.get("type")).upper() and "RECEIVED" not in str(a.get("type")).upper():
            tid = str(a.get("seasonTeamId"))
            if tid in h_ids: h += 1
            elif tid in g_ids: g += 1
    return min(h, 5), min(g, 5)

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
        for g in (last_games[:5] if last_games else []):
            with st.container(border=True):
                st.caption(f"{g.get('date','').split(' ')[0]}")
                st.write(f"vs {g.get('home') if team_name not in g.get('home') else g.get('guest')}")
                st.write(f"**{g.get('score')}**")

def analyze_scouting_data(team_id, detailed_games):
    stats = { "games_count": len(detailed_games), "wins": 0, "ato_stats": {"possessions": 0, "points": 0}, "start_stats": {"avg_diff": 0}, "rotation_depth": 0, "top_scorers": {} }
    tid_str = str(team_id)
    for box in detailed_games:
        is_h = box.get('meta_is_home', False)
        sh, sg = safe_int(box.get("result",{}).get("homeTeamFinalScore") or box.get("homeTeamPoints")), safe_int(box.get("result",{}).get("guestTeamFinalScore") or box.get("guestTeamPoints"))
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
        stats["start_stats"]["avg_diff"] += (hs - gs if is_h else gs - hs)
    cnt = stats["games_count"] or 1
    stats["rotation_depth"] = round(stats["rotation_depth"]/cnt, 1); stats["start_stats"]["avg_diff"] = round(stats["start_stats"]["avg_diff"]/cnt, 1)
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

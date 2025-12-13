import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import pytz
import openai # <-- Dieser Import MUSS hier oben stehen

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

def render_boxscore_table_pro(player_stats, team_name, coach_name="-"):
    if not player_stats: return

    data = []
    t_min=0; t_pts=0; t_fgm=0; t_fga=0; t_3pm=0; t_3pa=0; t_ftm=0; t_fta=0
    t_or=0; t_dr=0; t_tr=0; t_as=0; t_st=0; t_to=0; t_bs=0; t_pf=0; t_eff=0; t_pm=0

    for p in player_stats:
        info = p.get("seasonPlayer", {})
        name = f"{info.get('lastName', '')}, {info.get('firstName', '')}"
        nr = info.get("shirtNumber", "-")
        starter = "*" if p.get("isStartingFive") else ""
        sec = safe_int(p.get("secondsPlayed"))
        
        if sec > 0:
            t_min += sec
            min_str = f"{int(sec//60):02d}:{int(sec%60):02d}"
            pts = safe_int(p.get("points")); t_pts += pts
            m2 = safe_int(p.get("twoPointShotsMade")); a2 = safe_int(p.get("twoPointShotsAttempted"))
            p2 = safe_int(p.get("twoPointShotSuccessPercent"))
            m3 = safe_int(p.get("threePointShotsMade")); a3 = safe_int(p.get("threePointShotsAttempted"))
            p3 = safe_int(p.get("threePointShotSuccessPercent")); t_3pm += m3; t_3pa += a3
            mfg = safe_int(p.get("fieldGoalsMade")); afg = safe_int(p.get("fieldGoalsAttempted"))
            pfg = safe_int(p.get("fieldGoalsSuccessPercent")); t_fgm += mfg; t_fga += afg
            mft = safe_int(p.get("freeThrowsMade")); aft = safe_int(p.get("freeThrowsAttempted"))
            pft = safe_int(p.get("freeThrowsSuccessPercent")); t_ftm += mft; t_fta += aft
            oreb = safe_int(p.get("offensiveRebounds")); t_or += oreb
            dreb = safe_int(p.get("defensiveRebounds")); t_dr += dreb
            treb = safe_int(p.get("totalRebounds")); t_tr += treb
            ast = safe_int(p.get("assists")); t_as += ast
            stl = safe_int(p.get("steals")); t_st += stl
            tov = safe_int(p.get("turnovers")); t_to += tov
            blk = safe_int(p.get("blocks")); t_bs += blk
            pf = safe_int(p.get("foulsCommitted")); t_pf += pf
            eff = safe_int(p.get("efficiency")); t_eff += eff
            pm = safe_int(p.get("plusMinus")); t_pm += pm

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

    tot_fg_pct = int(t_fgm/t_fga*100) if t_fga else 0
    tot_3p_pct = int(t_3pm/t_3pa*100) if t_3pa else 0
    tot_ft_pct = int(t_ftm/t_fta*100) if t_fta else 0
    
    totals = {
        "No.": "", "Name": "TOTALS", "Min": "200:00", "PTS": t_pts,
        "2P": "", "3P": f"{t_3pm}/{t_3pa} ({tot_3p_pct}%)", "FG": f"{t_fgm}/{t_fga} ({tot_fg_pct}%)", 
        "FT": f"{t_ftm}/{t_fta} ({tot_ft_pct}%)", "OR": t_or, "DR": t_dr, "TR": t_tr, 
        "AS": t_as, "ST": t_st, "TO": t_to, "BS": t_bs, "PF": t_pf, "EFF": t_eff, "+/-": t_pm
    }
    data.append(totals)
    df = pd.DataFrame(data)
    
    def highlight_totals(row):
        return ['font-weight: bold; background-color: #f0f0f0' if row['Name'] == 'TOTALS' else '' for _ in row]

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

def generate_game_summary(box):
    """Generiert einen textbasierten Spielbericht."""
    if not box: return "Keine Daten verfügbar."

    h_data = box.get("homeTeam", {})
    g_data = box.get("guestTeam", {})
    h_name = get_team_name(h_data, "Heim")
    g_name = get_team_name(g_data, "Gast")
    res = box.get("result", {})
    
    s_h = res.get("homeTeamFinalScore", 0)
    s_g = res.get("guestTeamFinalScore", 0)
    
    # 1. Ergebnis
    winner = h_name if s_h > s_g else g_name
    diff = abs(s_h - s_g)
    text = f"**Endergebnis:** {h_name} {s_h} : {s_g} {g_name}\n\n"
    
    if diff < 6:
        text += f"In einem bis zur letzten Sekunde spannenden Krimi setzte sich {winner} knapp durch. "
    elif diff > 20:
        text += f"{winner} dominierte das Spiel deutlich und gewann souverän mit {diff} Punkten Vorsprung. "
    else:
        text += f"{winner} konnte das Spiel mit einem soliden {diff}-Punkte-Vorsprung für sich entscheiden. "

    # 2. Viertel-Analyse
    q_h_scores = [res.get(f"homeTeamQ{i}Score", 0) for i in range(1, 5)]
    q_g_scores = [res.get(f"guestTeamQ{i}Score", 0) for i in range(1, 5)]
    
    h_q_wins = sum(1 for i in range(4) if q_h_scores[i] > q_g_scores[i])
    if h_q_wins == 4 and s_h > s_g:
        text += f"{h_name} gewann dabei jedes einzelne Viertel. "
    elif h_q_wins == 0 and s_h < s_g:
        text += f"{g_name} ließ nichts anbrennen und entschied alle vier Viertel für sich. "
    
    # 3. Schlüsselstatistiken
    h_fg = safe_int(h_data.get("gameStat", {}).get("fieldGoalsSuccessPercent"))
    g_fg = safe_int(g_data.get("gameStat", {}).get("fieldGoalsSuccessPercent"))
    h_reb = safe_int(h_data.get("gameStat", {}).get("totalRebounds"))
    g_reb = safe_int(g_data.get("gameStat", {}).get("totalRebounds"))
    h_to = safe_int(h_data.get("gameStat", {}).get("turnovers"))
    g_to = safe_int(g_data.get("gameStat", {}).get("turnovers"))

    text += "\n\n**Schlüssel zum Sieg:**\n"
    if s_h > s_g:
        if h_fg > g_fg + 5: text += f"- {h_name} traf deutlich besser aus dem Feld ({h_fg}% vs {g_fg}%).\n"
        if h_reb > g_reb + 5: text += f"- Die Dominanz am Brett war entscheidend ({h_reb} zu {g_reb} Rebounds).\n"
        if h_to < g_to - 3: text += f"- {h_name} passte besser auf den Ball auf ({h_to} Turnover gegenüber {g_to}).\n"
    else:
        if g_fg > h_fg + 5: text += f"- {g_name} hatte die heißeren Hände ({g_fg}% vs {h_fg}% Trefferquote).\n"
        if g_reb > h_reb + 5: text += f"- {g_name} kontrollierte die Rebounds ({g_reb} zu {h_reb}).\n"
        if g_to < h_to - 3: text += f"- {g_name} erzwang viele Ballverluste ({h_to} Turnover beim Gegner).\n"

    # 4. Top Performer
    def get_best(p_list, key):
        if not p_list: return None, 0
        s = sorted(p_list, key=lambda x: safe_int(x.get(key)), reverse=True)
        p = s[0]
        name = p.get("seasonPlayer", {}).get("lastName", "Unknown")
        return name, safe_int(p.get(key))

    h_p_name, h_p_val = get_best(h_data.get("playerStats", []), "points")
    g_p_name, g_p_val = get_best(g_data.get("playerStats", []), "points")
    
    text += "\n**Top Performer:**\n"
    text += f"Auf Seiten von {h_name} war **{h_p_name}** mit {h_p_val} Punkten am erfolgreichsten. "
    text += f"Bei {g_name} hielt **{g_p_name}** mit {g_p_val} Zählern dagegen."

    return text

def generate_complex_ai_prompt(box):
    """
    Erstellt einen fertigen Prompt für ChatGPT basierend auf den Boxscore-Daten
    und den spezifischen SEO/Journalismus-Anforderungen.
    """
    if not box: return "Keine Daten."

    # 1. Datenaufbereitung
    h_data = box.get("homeTeam", {})
    g_data = box.get("guestTeam", {})
    h_name = get_team_name(h_data, "Heim")
    g_name = get_team_name(g_data, "Gast")
    res = box.get("result", {})
    
    # Identifikation VIMODROM (falls Jena spielt)
    is_jena_home = ("Jena" in h_name or "VIMODROM" in h_name)
    is_jena_guest = ("Jena" in g_name or "VIMODROM" in g_name)

    # Korrekte Bestimmung von VIMODROM Name und Gegner
    vimodrom_name = "VIMODROM Baskets Jena" 
    opponent = ""
    jena_score = 0
    opp_score = 0

    if is_jena_home:
        opponent = g_name
        jena_score = res.get("homeTeamFinalScore", 0)
        opp_score = res.get("guestTeamFinalScore", 0)
    elif is_jena_guest:
        opponent = h_name
        jena_score = res.get("guestTeamFinalScore", 0)
        opp_score = res.get("homeTeamFinalScore", 0)
    else: # Wenn Jena nicht spielt, neutral bleiben
        vimodrom_name = "" 
        opponent = "" # Kein direkter Gegner aus VIMODROM-Sicht
        jena_score = res.get("homeTeamFinalScore", 0) # Als Referenz
        opp_score = res.get("guestTeamFinalScore", 0) # Als Referenz


    # Viertel-Ergebnisse für den Kontext (immer Heim vs Gast)
    q_str = f"Q1: {res.get('homeTeamQ1Score', 0)}:{res.get('guestTeamQ1Score', 0)}, " \
            f"Q2: {res.get('homeTeamQ2Score', 0)}:{res.get('guestTeamQ2Score', 0)}, " \
            f"Q3: {res.get('homeTeamQ3Score', 0)}:{res.get('guestTeamQ3Score', 0)}, " \
            f"Q4: {res.get('homeTeamQ4Score', 0)}:{res.get('guestTeamQ4Score', 0)}"

    # Top Performer extrahieren
    def get_stats_str(team_data):
        s = team_data.get("gameStat", {})
        p_list = team_data.get("playerStats", [])
        # Top Scorer finden
        top_p = sorted([p for p in p_list if p.get("points", 0) is not None], key=lambda x: x.get("points", 0), reverse=True)[:2]
        top_str = ", ".join([f"{p.get('seasonPlayer', {}).get('lastName')} ({p.get('points')} Pkt)" for p in top_p])
        
        fg = safe_int(s.get("fieldGoalsSuccessPercent", 0))
        reb = safe_int(s.get("totalRebounds", 0))
        to = safe_int(s.get("turnovers", 0))
        ast = safe_int(s.get("assists", 0))
        
        return f"FG-Quote: {fg}%, Total Rebounds: {reb}, Turnovers: {to}, Assists: {ast}, Top-Scorer: {top_str}"

    stats_home = get_stats_str(h_data)
    stats_guest = get_stats_str(g_data)

    # 2. Der Prompt Text (Dein Wunsch-Prompt)
    prompt_sections = []

    prompt_sections.append("ANWEISUNGEN FÜR KI-GENERIERUNG:")
    prompt_sections.append("Schreibe immer in Deutsch. Die Texte müssen SEO-optimiert geschrieben werden, mit gezieltem Einsatz relevanter Keywords, semantischer Variationen und organischem Lesefluss. Vermeide Worte wie 'beeindruckend' und wähle präzisere oder neutralere Formulierungen.")
    
    if vimodrom_name:
        prompt_sections.append(f"AUFMERKSAMKEIT: Wenn in den folgenden Berichten die 'VIMODROM Baskets Jena' involviert sind, schreibe den ERSTEN Artikel (für die VIMODROM-Website) aus der Sicht der VIMODROM Baskets Jena (Fan-Brille, emotional). Alle anderen Artikel bleiben neutral.")
        prompt_sections.append(f"Relevante Keywords für Jena: VIMODROM Baskets Jena, Basketball in Jena, Basketball Training Jena, Basketballspiele Thüringen. Diese Keywords sollen in den Titel, die Meta-Beschreibung und den Textkörper integriert werden.")
        prompt_sections.append(f"Das Team für die Fan-Perspektive ist: {vimodrom_name}")

    prompt_sections.append("\n\nSPIELDATEN FÜR DIE TEXTE:")
    prompt_sections.append(f"- Heimteam: {h_name}")
    prompt_sections.append(f"- Gastteam: {g_name}")
    prompt_sections.append(f"- Endergebnis: {h_name} {res.get('homeTeamFinalScore', 0)} : {res.get('guestTeamFinalScore', 0)} {g_name}")
    prompt_sections.append(f"- Viertelverlauf: {q_str}")
    prompt_sections.append(f"- Statistik {h_name}: {stats_home}")
    prompt_sections.append(f"- Statistik {g_name}: {stats_guest}")
    prompt_sections.append(f"- Zuschauer: {res.get('spectators', 'k.A.')}")
    prompt_sections.append(f"- Halle: {box.get('venue', {}).get('name', 'der Halle')}")

    if is_jena_home or is_jena_guest:
        prompt_sections.append(f"- VIMODROM Baskets Jena spielte gegen: {opponent}")
        prompt_sections.append(f"- VIMODROM Ergebnis: {jena_score} : {opp_score} gegen {opponent}")
    
    prompt_sections.append("\n\nAUFGABE 1: ERSTELLE DREI JOURNALISTISCHE SPIELBERICHTE")
    prompt_sections.append("Ziel: Atmosphäre und Dramatik des Basketballspiels einfangen.")
    prompt_sections.append("Sprache: Klar, prägnant, lebhafte Beschreibungen, emotionale Höhepunkte.")
    prompt_sections.append("Texte zugänglich für Gelegenheitssportfans, detailliert genug für Experten.")
    prompt_sections.append("Länge: Texte für Website und 2. DBBL Website jeweils mindestens 3000 Zeichen umfassen. Für das Spieltagsmagazin 1500-2000 Zeichen.")
    prompt_sections.append("Am Ende jedes Artikels sollen jeweils drei verschiedene Headlines, zehn Keywords (kommagetrennt) und eine Meta-Beschreibung (maximal 150 Zeichen) bereitgestellt werden.")

    prompt_sections.append("\n### ARTIKEL 1: Für die VIMODROM-Website")
    prompt_sections.append("Perspektive: Aus Sicht der VIMODROM Baskets Jena (fan-nah, emotional, Fokus auf das Jena-Team).")
    prompt_sections.append("Beginne mit einem überraschenden Moment oder einer besonderen Aussage aus dem Spiel (fiktiv, wenn keine da).")
    prompt_sections.append("Beschreibe den Spielverlauf mit Fokus auf unerwartete Wendungen, taktische Feinheiten und herausragende Szenen des Jena-Teams.")
    prompt_sections.append("Integriere Statistiken kreativ und erzähle Geschichten hinter den Zahlen (Fokus Jena-Spieler).")
    prompt_sections.append("Betone die Leistungen weniger beachteter Jena-Spielerinnen und hebe einzigartige Aspekte des Jena-Spiels hervor.")
    prompt_sections.append("Gezielt anzusprechende Emotionen: Spannung, Begeisterung, Teamgeist, Stolz, Adrenalin/Nervenkitzel, Hoffnung, Mitfiebern/Identifikation.")

    prompt_sections.append("\n### ARTIKEL 2: Für die 2. DBBL-Website")
    prompt_sections.append("Perspektive: Neutral, objektiv, journalistisch (keine Fan-Brille).")
    prompt_sections.append("Der Text soll die Fakten des Spiels präzise darstellen, aber dennoch die Dramatik einfangen.")
    prompt_sections.append("Struktur: Beginne mit der Einordnung des Spiels in den Saisonkontext, gefolgt von einer Analyse des Gegners, aktuellen Spieler- und Trainerzitaten (fiktiv, wenn nicht vorhanden) sowie relevanten Verletzungsupdates (fiktiv, wenn nicht vorhanden).")
    prompt_sections.append("Gezielt anzusprechende Emotionen: Spannung, Begeisterung, Adrenalin/Nervenkitzel, Neugierde.")

    prompt_sections.append("\n### ARTIKEL 3: Für das Spieltagsmagazin")
    prompt_sections.append("Perspektive: Aus heutiger Perspektive als Rückblick, emotional und fesselnd.")
    prompt_sections.append("Fokus auf die Story des Spiels, die wichtigsten Phasen und Highlights.")
    prompt_sections.append("Kann etwas freier im Stil sein, weniger formell als die Website-Texte.")
    prompt_sections.append("Gezielt anzusprechende Emotionen: Erleichterung (wenn gewonnen), Stolz, Begeisterung, Mitfiebern.")

    prompt_sections.append("\n\nAUFGABE 2: ERSTELLE EINEN SEO-OPTIMIERTEN WEBSITE-TEXT ZUM THEMA 'Basketball in Jena'")
    prompt_sections.append("Ziel: Sport- und Basketballinteressierte aller Altersklassen ansprechen.")
    prompt_sections.append("Inhalt: Vorstellung des Teams VIMODROM Baskets Jena, Informationen zu anstehenden Spielen, Trainingstipps und Möglichkeiten für neue Spieler, dem Team beizutreten.")
    prompt_sections.append("Struktur: Klare Struktur ohne Zwischenüberschriften. Absätze kurz und prägnant (max. 3 Sätze pro Absatz).")
    prompt_sections.append("Länge: Mindestens 600–1.000 Wörter.")
    prompt_sections.append("Keywords: VIMODROM Baskets Jena, Basketball in Jena, Basketball Training Jena, Basketballspiele Thüringen (in Titel, Meta-Beschreibung und Textkörper integrieren).")
    prompt_sections.append("Meta-Beschreibung: Maximal 150 Zeichen, spannend und klickstark.")
    prompt_sections.append("Engagement fördern: Internen Links (fiktiv) zu weiteren Artikeln (z. B. Trainingszeiten, Ticketkauf) und externen Links (fiktiv) zu vertrauenswürdigen Basketballseiten integrieren.")
    prompt_sections.append("Multimedia: Platzhalter für Bilder oder Videos mit Alt-Tags (z.B. `<img src='bild-url.jpg' alt='Basketball Training VIMODROM Baskets Jena'>`).")
    prompt_sections.append("Inhalt an Suchintent anpassen, inspiriert für das Team und Basketball in Jena.")

    prompt_sections.append("\n\nZUSAMMENFASSUNG UND META-INFORMATIONEN:")
    prompt_sections.append("Wenn alle Berichte geschrieben sind, füge zusätzlich EINE Zusammenfassung mit 10 Meta-Tags (kommagetrennt) und EINER Meta-Beschreibung für das GESAMTE SPIEL hinzu.")

    return "\n".join(prompt_sections)

def run_openai_generation(api_key, prompt):
    """Sendet den Prompt an die OpenAI API und gibt den Text zurück."""
    client = openai.OpenAI(api_key=api_key)
    
    try:
        # Wir nutzen gpt-4o, da es aktuell das beste Preis-Leistungs-Verhältnis hat
        # und sehr gut Deutsch schreibt.
        response = client.chat.completions.create(
            model="gpt-4o", 
            messages=[
                {"role": "system", "content": "Du bist ein professioneller Sportjournalist und SEO-Experte, spezialisiert auf Basketball. Du schreibst fundierte, lebendige und optimierte Artikel für verschiedene Zielgruppen."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0, # Etwas niedriger, da der Prompt schon sehr spezifisch ist
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Fehler bei der API-Abfrage: {str(e)}"

# --- Fügen Sie dies am Ende von src/analysis_ui.py hinzu ---

def generate_complex_ai_prompt(box):
    """
    Erstellt einen fertigen Prompt für ChatGPT basierend auf den Boxscore-Daten
    und den spezifischen SEO/Journalismus-Anforderungen.
    """
    if not box: return "Keine Daten."

    # 1. Datenaufbereitung
    h_data = box.get("homeTeam", {})
    g_data = box.get("guestTeam", {})
    h_name = get_team_name(h_data, "Heim")
    g_name = get_team_name(g_data, "Gast")
    res = box.get("result", {})
    
    # Identifikation VIMODROM (falls Jena spielt)
    is_jena_home = "Jena" in h_name or "VIMODROM" in h_name
    opponent = g_name if is_jena_home else h_name
    jena_score = res.get("homeTeamFinalScore", 0) if is_jena_home else res.get("guestTeamFinalScore", 0)
    opp_score = res.get("guestTeamFinalScore", 0) if is_jena_home else res.get("homeTeamFinalScore", 0)
    
    # Viertel-Ergebnisse für den Kontext
    q_str = f"Q1: {res.get('homeTeamQ1Score')}:{res.get('guestTeamQ1Score')}, " \
            f"Q2: {res.get('homeTeamQ2Score')}:{res.get('guestTeamQ2Score')}, " \
            f"Q3: {res.get('homeTeamQ3Score')}:{res.get('guestTeamQ3Score')}, " \
            f"Q4: {res.get('homeTeamQ4Score')}:{res.get('guestTeamQ4Score')}"

    # Top Performer extrahieren
    def get_stats_str(team_data):
        s = team_data.get("gameStat", {})
        p_list = team_data.get("playerStats", [])
        # Top Scorer finden
        top_p = sorted([p for p in p_list if p.get("points", 0) is not None], key=lambda x: x.get("points", 0), reverse=True)[:2]
        top_str = ", ".join([f"{p.get('seasonPlayer', {}).get('lastName')} ({p.get('points')} Pkt)" for p in top_p])
        
        fg = s.get("fieldGoalsSuccessPercent", 0)
        reb = s.get("totalRebounds", 0)
        to = s.get("turnovers", 0)
        return f"FG: {fg}%, Reb: {reb}, TO: {to}, Top-Scorer: {top_str}"

    stats_home = get_stats_str(h_data)
    stats_guest = get_stats_str(g_data)

    # 2. Der Prompt Text (Dein Wunsch-Prompt)
    prompt = f"""
Ich habe hier die Daten eines Basketballspiels. Bitte schreibe basierend auf diesen Daten und den folgenden Anweisungen die Berichte.

DATEN DES SPIELS:
- Heimteam: {h_name}
- Gastteam: {g_name}
- Endergebnis: {res.get("homeTeamFinalScore")} : {res.get("guestTeamFinalScore")}
- Viertelverlauf: {q_str}
- Statistik {h_name}: {stats_home}
- Statistik {g_name}: {stats_guest}
- Zuschauer: {res.get("spectators", "k.A.")}
- Halle: {box.get("venue", {}).get("name", "Halle")}

ANWEISUNGEN:
Schreibe immer in Deutsch und aus der Sicht der VIMODROM Baskets Jena (falls sie gespielt haben, sonst neutral) für die Website-Texte. 
Gegner ist: {opponent}.

AUFGABE 1: Schreibe drei dynamische, SEO-optimierte, journalistische Artikel.
1. Artikel: Für die VIMODROM-Website (Fan-Brille, emotional).
2. Artikel: Für die 2. DBBL-Website (Neutral, journalistisch).
3. Artikel: Für das Spieltagsmagazin (Rückblick aus heutiger Perspektive).

Anforderungen:
- Ziel: Atmosphäre und Dramatik einfangen.
- Sprache: Klar, prägnant, lebhafte Beschreibungen, emotionale Höhepunkte.
- Länge: Website und DBBL Texte mind. 3000 Zeichen (bitte ausführlich schreiben!).
- Footer pro Artikel: 3 Headlines, 10 Keywords, 1 Meta-Beschreibung.
- Ganz am Ende: Zusammenfassung mit 10 Meta-Tags.

AUFGABE 2: Erstelle einen SEO-optimierten Text "Basketball in Jena".
- Keywords: VIMODROM Baskets Jena, Basketball in Jena, Basketball Training Jena.
- Struktur: Keine Zwischenüberschriften, kurze Absätze.
- Inhalt: Mehrwert, Teamvorstellung, Trainingstipps.
- Länge: 600-1000 Wörter.

STIL-GUIDE & EMOTIONEN:
- Vermeide das Wort "beeindruckend".
- Nutze Emotionen: Spannung (bei engem Spiel), Begeisterung (Dunks/Plays), Teamgeist, Stolz.
- Wenn das Spiel eng war ({abs(jena_score - opp_score)} Punkte Differenz), betone die Spannung und den "Nervenkitzel".
- Wenn es deutlich war, betone die "Dominanz" oder den "Kampfgeist trotz Niederlage".
- Integriere die Statistiken kreativ in den Fließtext (erzähle die Geschichte hinter den Zahlen).

Bitte starte jetzt mit der Erstellung der Texte.
"""
    return prompt

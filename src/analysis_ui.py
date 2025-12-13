import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import pytz

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
    """
    Sucht den Teamnamen extrem gründlich in allen möglichen Feldern.
    """
    if not team_data: return default_name
    
    # 1. Direkter Name (oft in 'details')
    if team_data.get("name"): return team_data.get("name")
    
    # 2. Im seasonTeam Objekt (oft in 'boxscore')
    season_team = team_data.get("seasonTeam", {})
    if season_team.get("name"): return season_team.get("name")
    
    # 3. Im gameStat -> seasonTeam (tief verschachtelt)
    game_stat = team_data.get("gameStat", {})
    season_team_nested = game_stat.get("seasonTeam", {})
    if season_team_nested.get("name"): return season_team_nested.get("name")
    
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
    """Header mit Teamnamen, Logo-Platzhaltern und Ergebnis."""
    h_data = details.get("homeTeam", {})
    g_data = details.get("guestTeam", {})
    
    # Robuste Namenssuche
    h_name = get_team_name(h_data, "Heim")
    g_name = get_team_name(g_data, "Gast")
    
    res = details.get("result", {})
    score_h = res.get("homeTeamFinalScore", 0)
    score_g = res.get("guestTeamFinalScore", 0)
    
    # Meta
    time_str = format_date_time(details.get("scheduledTime"))
    
    venue = details.get("venue", {})
    venue_str = venue.get("name", "-")
    address = venue.get("address", "")
    if address and isinstance(address, str):
        parts = address.split(",")
        if len(parts) > 1: venue_str += f", {parts[-1].strip()}"

    # Schiris
    refs = []
    for i in range(1, 4):
        r = details.get(f"referee{i}")
        if r and isinstance(r, dict):
             fn = r.get("firstName", ""); ln = r.get("lastName", "")
             if fn or ln: refs.append(f"{ln} {fn}".strip())
             elif r.get("refId"): refs.append(f"Ref#{r.get('refId')}")
    ref_str = ", ".join(refs) if refs else "-"
    att = res.get("spectators", "-")
    
    # --- LAYOUT ---
    st.markdown(f"<div style='text-align: center; color: #666; margin-bottom: 10px; font-size: 1.1em;'>📍 {venue_str} | 🕒 {time_str}</div>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([2, 1, 2])
    with c1:
        st.markdown(f"## {h_name}")
    with c2:
        st.markdown(f"<h1 style='text-align: center;'>{score_h} : {score_g}</h1>", unsafe_allow_html=True)
        # QUARTER TABLE
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
    """Boxscore Tabelle mit Coach darunter."""
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
    
    # Coach unter der Tabelle
    if coach_name and coach_name != "-":
        st.markdown(f"*Head Coach: {coach_name}*")

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

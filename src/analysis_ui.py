import streamlit as st
import pandas as pd
import altair as alt

def safe_int(val):
    """Wandelt Werte sicher in Zahlen um."""
    if val is None: return 0
    if isinstance(val, int): return val
    if isinstance(val, float): return int(val)
    if isinstance(val, str):
        if val.strip() == "": return 0
        try: return int(float(val))
        except: return 0
    return 0

def get_team_name(team_data, default_name="Team"):
    """Sucht den Teamnamen."""
    name = team_data.get("gameStat", {}).get("seasonTeam", {}).get("name")
    if name: return name
    name = team_data.get("seasonTeam", {}).get("name")
    if name: return name
    name = team_data.get("name")
    if name: return name
    return default_name

def calculate_advanced_stats_from_actions(actions, home_id, guest_id):
    """
    Berechnet Runs, Leads und Advanced Stats aus dem Play-by-Play (actions).
    """
    if not actions:
        return {}

    # Initialisierung
    stats = {
        "h_lead": 0, "g_lead": 0,
        "h_run": 0, "g_run": 0,
        "h_paint": 0, "g_paint": 0,
        "h_2nd": 0, "g_2nd": 0,
        "h_fb": 0, "g_fb": 0
    }

    current_h_score = 0
    current_g_score = 0
    
    # Für Runs
    current_run_team = None
    current_run_score = 0

    for act in actions:
        # 1. Scores updaten (Achtung: API liefert oft den Score NACH der Aktion)
        h_score_now = safe_int(act.get("homeTeamPoints"))
        g_score_now = safe_int(act.get("guestTeamPoints"))
        
        # Punkte in dieser Aktion
        delta_h = h_score_now - current_h_score
        delta_g = g_score_now - current_g_score
        
        # Scoring Run Logik
        if delta_h > 0:
            if current_run_team == "home":
                current_run_score += delta_h
            else:
                current_run_team = "home"
                current_run_score = delta_h
            if current_run_score > stats["h_run"]: stats["h_run"] = current_run_score
            
        elif delta_g > 0:
            if current_run_team == "guest":
                current_run_score += delta_g
            else:
                current_run_team = "guest"
                current_run_score = delta_g
            if current_run_score > stats["g_run"]: stats["g_run"] = current_run_score
            
        # Biggest Lead Logik
        diff = h_score_now - g_score_now
        if diff > 0 and diff > stats["h_lead"]: stats["h_lead"] = diff
        if diff < 0 and abs(diff) > stats["g_lead"]: stats["g_lead"] = abs(diff)
        
        # Advanced Stats (Paint, FB, 2nd)
        # Wir suchen in 'qualifiers' (Liste von Strings) oder 'type'
        # HINWEIS: Die genauen Strings hängen von der API ab. Ich nehme Standard-Werte an.
        qualifiers = act.get("qualifiers", [])
        # Manchmal ist qualifiers ein String, manchmal eine Liste
        if isinstance(qualifiers, str): qualifiers = [qualifiers]
        qualifiers = [str(q).lower() for q in qualifiers] # Alles klein schreiben
        
        action_type = str(act.get("type", "")).lower()
        
        # Team Zuordnung der Aktion
        # seasonTeamId in der Action vergleichen
        act_team_id = str(act.get("seasonTeamId", ""))
        
        points = delta_h + delta_g # Punkte in dieser Aktion
        
        if points > 0:
            is_home = (act_team_id == str(home_id))
            
            # Fastbreak
            if "fastbreak" in qualifiers or "fastbreak" in action_type:
                if is_home: stats["h_fb"] += points
                else: stats["g_fb"] += points
                
            # Paint (Oft als 'PITP' oder 'paint' markiert)
            if "paint" in qualifiers or "inside" in qualifiers:
                if is_home: stats["h_paint"] += points
                else: stats["g_paint"] += points
                
            # 2nd Chance (Oft als 'second_chance' markiert)
            if "second" in qualifiers or "2nd" in qualifiers:
                if is_home: stats["h_2nd"] += points
                else: stats["g_2nd"] += points

        # Update für nächste Runde
        current_h_score = h_score_now
        current_g_score = g_score_now

    return stats

def render_game_header(box):
    """Header mit allen Meta-Infos."""
    h_data = box.get("homeTeam", {})
    g_data = box.get("guestTeam", {})
    h_name = get_team_name(h_data, "Heim")
    g_name = get_team_name(g_data, "Gast")
    h_coach = h_data.get("headCoachName", "-")
    g_coach = g_data.get("headCoachName", "-")
    score_h = safe_int(h_data.get("gameStat", {}).get("points"))
    score_g = safe_int(g_data.get("gameStat", {}).get("points"))
    
    # Meta Daten
    time_str = box.get("scheduledTime", "")[:16].replace("T", " ")
    
    refs = []
    for i in range(1, 4):
        r = box.get(f"referee{i}")
        if r and isinstance(r, dict):
            fn = r.get("firstName", ""); ln = r.get("lastName", "")
            if not fn and not ln: fn = r.get("name", "")
            full = f"{ln} {fn}".strip()
            if full: refs.append(full)
    ref_str = ", ".join(refs) if refs else "-"
    
    att = box.get("attendance")
    if not att: att = h_data.get("gameStat", {}).get("attendance", "-")
    
    venue = box.get("venue", {})
    venue_str = venue.get("name", "-") if isinstance(venue, dict) else "-"

    # Layout
    st.markdown(f"<div style='text-align: center; color: #666; margin-bottom: 10px;'>{time_str} | {venue_str}</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([2, 1, 2])
    with c1:
        st.markdown(f"## {h_name}")
        st.caption(f"HC: {h_coach}")
    with c2:
        st.markdown(f"<h1 style='text-align: center;'>{score_h} : {score_g}</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray;'>FINAL</p>", unsafe_allow_html=True)
    with c3:
        st.markdown(f"## {g_name}")
        st.caption(f"HC: {g_coach}")
    
    st.write("---")
    st.markdown(f"""
    <div style='display: flex; justify-content: space-between; color: #333; font-size: 14px; background-color: #f9f9f9; padding: 10px; border-radius: 5px;'>
        <span>👥 <b>Zuschauer:</b> {att}</span>
        <span>⚖️ <b>Schiedsrichter:</b> {ref_str}</span>
        <span>ID: {box.get('gameId', box.get('id', '-'))}</span>
    </div>
    """, unsafe_allow_html=True)

def render_boxscore_table_pro(player_stats, team_name):
    """Boxscore Tabelle ohne Scrollbalken."""
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
        "2P": "", "3P": f"{t_3pm}/{t_3pa} ({tot_3p_pct}%)",
        "FG": f"{t_fgm}/{t_fga} ({tot_fg_pct}%)", "FT": f"{t_ftm}/{t_fta} ({tot_ft_pct}%)",
        "OR": t_or, "DR": t_dr, "TR": t_tr, "AS": t_as, "ST": t_st, "TO": t_to, "BS": t_bs,
        "PF": t_pf, "EFF": t_eff, "+/-": t_pm
    }
    data.append(totals)
    df = pd.DataFrame(data)
    
    def highlight_totals(row):
        return ['font-weight: bold; background-color: #f0f0f0' if row['Name'] == 'TOTALS' else '' for _ in row]

    st.markdown(f"#### {team_name}")
    calc_height = (len(df) + 1) * 35 + 3
    st.dataframe(df.style.apply(highlight_totals, axis=1), hide_index=True, use_container_width=True, height=calc_height)

def render_charts_and_stats(box):
    """Charts und Tabelle (Mit berechneten Advanced Stats)."""
    
    h_data = box.get("homeTeam", {})
    g_data = box.get("guestTeam", {})
    h = h_data.get("gameStat", {})
    g = g_data.get("gameStat", {})
    
    h_name = get_team_name(h_data, "Heim")
    g_name = get_team_name(g_data, "Gast")
    
    # --- CALCULATE ADVANCED STATS FROM PLAY-BY-PLAY ---
    actions = box.get("actions", [])
    
    # IDs holen für Zuordnung
    hid = h_data.get("seasonTeam", {}).get("seasonTeamId", "0")
    gid = g_data.get("seasonTeam", {}).get("seasonTeamId", "0")
    
    calc_stats = calculate_advanced_stats_from_actions(actions, hid, gid)
    
    # Werte zusammenführen (API vs. Berechnet)
    # Wenn API Werte hat (oft "-"), nutzen wir unsere berechneten
    h_paint = calc_stats.get("h_paint", 0)
    g_paint = calc_stats.get("g_paint", 0)
    
    h_2nd = calc_stats.get("h_2nd", 0)
    g_2nd = calc_stats.get("g_2nd", 0)
    
    h_fb = calc_stats.get("h_fb", 0)
    g_fb = calc_stats.get("g_fb", 0)
    
    h_lead = calc_stats.get("h_lead", 0)
    g_lead = calc_stats.get("g_lead", 0)
    
    h_run = calc_stats.get("h_run", 0)
    g_run = calc_stats.get("g_run", 0)

    # --- CHARTS ---
    def mk_label(pct, made, att):
        return f"{pct}% ({made}/{att})"

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

    base = alt.Chart(source).encode(
        x=alt.X('Cat', sort=categories, title=None, axis=alt.Axis(labelAngle=0, labelFontWeight='bold')),
        xOffset='Team',
        y=alt.Y('Pct', title=None, axis=None)
    )
    bar = base.mark_bar().encode(
        color=alt.Color('Team', legend=alt.Legend(title=None, orient='top')),
        tooltip=['Team', 'Cat', 'Label']
    )
    text = base.mark_text(dy=-10, color='black').encode(text='Label')
    chart = (bar + text).properties(height=350)

    # --- TABELLE ---
    metrics = [
        ("Offensive Rebounds", safe_int(h.get('offensiveRebounds')), safe_int(g.get('offensiveRebounds'))),
        ("Defensive Rebounds", safe_int(h.get('defensiveRebounds')), safe_int(g.get('defensiveRebounds'))),
        ("Total Rebounds", safe_int(h.get('totalRebounds')), safe_int(g.get('totalRebounds'))),
        ("Assists", safe_int(h.get("assists")), safe_int(g.get("assists"))),
        ("Fouls", safe_int(h.get("foulsCommitted")), safe_int(g.get("foulsCommitted"))),
        ("Turnovers", safe_int(h.get("turnovers")), safe_int(g.get("turnovers"))),
        ("Steals", safe_int(h.get("steals")), safe_int(g.get("steals"))),
        ("Blocks", safe_int(h.get("blocks")), safe_int(g.get("blocks"))),
        # HIER DIE BERECHNETEN WERTE
        ("Points in Paint", h_paint, g_paint),
        ("2nd Chance Pts", h_2nd, g_2nd),
        ("Fastbreak Pts", h_fb, g_fb),
        ("Biggest Lead", h_lead, g_lead),
        ("Biggest Run", h_run, g_run)
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

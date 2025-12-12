import streamlit as st
import pandas as pd
import altair as alt

def safe_int(val):
    """Hilfsfunktion: Wandelt Wert in Int um, 0 wenn leer."""
    if val is None or val == "": return 0
    try: return int(val)
    except: return 0

def render_game_header(box):
    """Zeigt den Header mit echten Teamnamen und Scores."""
    # Teamnamen sicher auslesen
    h_team = box.get("homeTeam", {})
    g_team = box.get("guestTeam", {})
    
    # Versuche den Namen an verschiedenen Stellen zu finden
    h_name = h_team.get("seasonTeam", {}).get("name", h_team.get("name", "Heim"))
    g_name = g_team.get("seasonTeam", {}).get("name", g_team.get("name", "Gast"))
    
    # Coaches
    h_coach = h_team.get("headCoachName", "-")
    g_coach = g_team.get("headCoachName", "-")
    
    # Ergebnis & Quarter
    h_stats = h_team.get("gameStat", {})
    g_stats = g_team.get("gameStat", {})
    
    score_h = h_stats.get("points", 0)
    score_g = g_stats.get("points", 0)
    
    # Q1-Q4 (API liefert diese oft nicht direkt, wir simulieren die Anzeige oder nutzen Totals)
    # Da die API im Beispiel keine Quarter-Daten liefert, zeigen wir nur den Endstand groß an
    
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
    st.caption(f"Zuschauer: {box.get('attendance', '-')} | Status: {box.get('status', 'OFFICIAL')}")

def render_boxscore_table_pro(player_stats, team_name):
    """Boxscore Tabelle ohne Scrollbalken und mit DNP."""
    if not player_stats: return

    data = []
    
    # Summen
    t_min=0; t_pts=0; t_fgm=0; t_fga=0; t_3pm=0; t_3pa=0; t_ftm=0; t_fta=0
    t_or=0; t_dr=0; t_tr=0; t_as=0; t_st=0; t_to=0; t_bs=0; t_pf=0; t_eff=0; t_pm=0

    for p in player_stats:
        info = p.get("seasonPlayer", {})
        name = f"{info.get('lastName', '')}, {info.get('firstName', '')}"
        nr = info.get("shirtNumber", "-")
        starter = "*" if p.get("isStartingFive") else ""
        
        # Zeit
        sec = safe_int(p.get("secondsPlayed"))
        if sec > 0:
            t_min += sec
            min_str = f"{int(sec//60):02d}:{int(sec%60):02d}"
        else:
            min_str = "DNP" # Did Not Play

        # Stats nur zählen wenn gespielt
        if sec > 0:
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

            # Strings
            s_2p = f"{m2}/{a2} ({p2}%)" if a2 else ""
            s_3p = f"{m3}/{a3} ({p3}%)" if a3 else ""
            s_fg = f"{mfg}/{afg} ({pfg}%)"
            s_ft = f"{mft}/{aft} ({pft}%)" if aft else ""
        else:
            # Leere Werte für DNP
            pts=0; s_2p=""; s_3p=""; s_fg=""; s_ft=""; oreb=0; dreb=0; treb=0
            ast=0; stl=0; tov=0; blk=0; pf=0; eff=0; pm=0

        data.append({
            "No.": f"{starter}{nr}", "Name": name, "Min": min_str, "PTS": pts,
            "2P": s_2p, "3P": s_3p, "FG": s_fg, "FT": s_ft,
            "OR": oreb, "DR": dreb, "TR": treb, "AS": ast, "ST": stl, "TO": tov, "BS": blk,
            "PF": pf, "EFF": eff, "+/-": pm
        })

    # TOTALS
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
    
    # Styling für Fettdruck der letzten Zeile
    def highlight_totals(row):
        return ['font-weight: bold; background-color: #f0f0f0' if row['Name'] == 'TOTALS' else '' for _ in row]

    st.markdown(f"#### {team_name}")
    # height Parameter sorgt dafür, dass kein Scrollbalken kommt (wenn hoch genug)
    st.dataframe(df.style.apply(highlight_totals, axis=1), hide_index=True, use_container_width=True, height=500)

def render_charts_and_stats(box):
    """Zeigt die Balkendiagramme und die Tabelle."""
    
    h = box.get("homeTeam", {}).get("gameStat", {})
    g = box.get("guestTeam", {}).get("gameStat", {})
    
    # Namen sicher holen
    h_data = box.get("homeTeam", {})
    g_data = box.get("guestTeam", {})
    h_name = h_data.get("seasonTeam", {}).get("name", "Heim")
    g_name = g_data.get("seasonTeam", {}).get("name", "Gast")

    # --- 1. CHART DATEN VORBEREITEN ---
    # Wir bauen Labels wie "45% (43/95)"
    def mk_label(pct, made, att):
        return f"{pct}% ({made}/{att})"

    categories = ["Field Goals", "2 Points", "3 Points", "Free Throws"]
    
    # Heim Daten
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
    
    # Gast Daten
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

    # Altair Chart
    base = alt.Chart(source).encode(
        x=alt.X('Cat', sort=categories, title=None, axis=alt.Axis(labelAngle=0, labelFontWeight='bold')),
        xOffset='Team',
        y=alt.Y('Pct', title=None, axis=None) # Y-Achse ausblenden
    )

    bar = base.mark_bar().encode(
        color=alt.Color('Team', legend=alt.Legend(title=None, orient='top')),
        tooltip=['Team', 'Cat', 'Label']
    )

    text = base.mark_text(dy=-10, color='black').encode(
        text='Label'
    )

    chart = (bar + text).properties(height=350)

    # --- 2. TABELLE VORBEREITEN ---
    metrics = [
        ("Rebounds OR/DR/TR", 
         f"{safe_int(h.get('offensiveRebounds'))}/{safe_int(h.get('defensiveRebounds'))}/{safe_int(h.get('totalRebounds'))}",
         f"{safe_int(g.get('offensiveRebounds'))}/{safe_int(g.get('defensiveRebounds'))}/{safe_int(g.get('totalRebounds'))}"),
        ("Assists", safe_int(h.get("assists")), safe_int(g.get("assists"))),
        ("Fouls", safe_int(h.get("foulsCommitted")), safe_int(g.get("foulsCommitted"))),
        ("Turnovers", safe_int(h.get("turnovers")), safe_int(g.get("turnovers"))),
        ("Steals", safe_int(h.get("steals")), safe_int(g.get("steals"))),
        ("Points in Paint", h.get("pointsInPaint", "-"), g.get("pointsInPaint", "-")),
        ("2nd Chance Pts", h.get("secondChancePoints", "-"), g.get("secondChancePoints", "-")),
        ("Fastbreak Pts", h.get("fastBreakPoints", "-"), g.get("fastBreakPoints", "-")),
        ("Biggest Lead", h.get("biggestLead", "-"), g.get("biggestLead", "-")),
        ("Biggest Run", h.get("biggestScoringRun", "-"), g.get("biggestScoringRun", "-"))
    ]

    # --- 3. LAYOUT ---
    st.altair_chart(chart, use_container_width=True)
    
    st.write("")
    
    # HTML Tabelle (jetzt OHNE Einrückung um den Fehler zu beheben)
    html_table = f"""<table style="width:100%; border-collapse: collapse; font-family: sans-serif; font-size: 14px;">
<tr style="background-color:#003366; color:white;">
<th style="padding:8px; text-align:center; width:40%;">{h_name}</th>
<th style="padding:8px; text-align:center; width:20%;">VS</th>
<th style="padding:8px; text-align:center; width:40%;">{g_name}</th>
</tr>"""

    for label, vh, vg in metrics:
        html_table += f"""<tr style="border-bottom:1px solid #eee;">
<td style="padding:6px; text-align:center;">{vh}</td>
<td style="padding:6px; text-align:center; font-weight:bold; color:#555; white-space:nowrap;">{label}</td>
<td style="padding:6px; text-align:center;">{vg}</td>
</tr>"""
    
    html_table += "</table>"
    st.markdown(html_table, unsafe_allow_html=True)

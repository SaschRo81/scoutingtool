import streamlit as st
import pandas as pd
import altair as alt

def safe_int(val):
    """Wandelt Werte sicher in Zahlen um, auch wenn sie leer oder Text sind."""
    if val is None: return 0
    if isinstance(val, int): return val
    if isinstance(val, float): return int(val)
    if isinstance(val, str):
        if val.strip() == "": return 0
        try: return int(float(val))
        except: return 0
    return 0

def get_team_name(team_data, default_name="Team"):
    """Sucht den Teamnamen in den verschiedenen Ebenen der API-Antwort."""
    name = team_data.get("gameStat", {}).get("seasonTeam", {}).get("name")
    if name: return name
    name = team_data.get("seasonTeam", {}).get("name")
    if name: return name
    name = team_data.get("name")
    if name: return name
    return default_name

def render_game_header(box):
    """Zeigt den Header mit Teamnamen, Ergebnis, Schiris und Zuschauern."""
    h_data = box.get("homeTeam", {})
    g_data = box.get("guestTeam", {})
    
    h_name = get_team_name(h_data, "Heim")
    g_name = get_team_name(g_data, "Gast")
    
    h_coach = h_data.get("headCoachName", "-")
    g_coach = g_data.get("headCoachName", "-")
    
    score_h = safe_int(h_data.get("gameStat", {}).get("points"))
    score_g = safe_int(g_data.get("gameStat", {}).get("points"))
    
    # --- SCHIEDSRICHTER SUCHEN ---
    refs = []
    for i in range(1, 4):
        r = box.get(f"referee{i}")
        if r and isinstance(r, dict):
            # Name zusammenbauen
             name = f"{r.get('firstName', '')} {r.get('lastName', '')}".strip()
             if name: refs.append(name)
    
    ref_str = ", ".join(refs) if refs else "-"
    # -----------------------------

    # ZUSCHAUER & ORT
    # Zuschauer oft direkt im Root oder im gameStat
    att = box.get("attendance")
    if not att: att = h_data.get("gameStat", {}).get("attendance", "-")
    
    # Ort (Venue) ist oft in der 'facility' im Schedule, hier im Boxscore evtl. nicht immer da
    # Wir lassen es erstmal weg, wenn nicht da.

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
    
    # Meta-Zeile mit Schiris
    st.markdown(f"""
    <div style='display: flex; justify-content: space-between; color: #555; font-size: 14px;'>
        <span><b>Zuschauer:</b> {att}</span>
        <span><b>Schiedsrichter:</b> {ref_str}</span>
        <span><b>Status:</b> {box.get('status', 'OFFICIAL')}</span>
    </div>
    """, unsafe_allow_html=True)

def render_boxscore_table_pro(player_stats, team_name):
    """Erstellt die Boxscore-Tabelle mit dynamischer Höhe (kein Scrollbalken)."""
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

    # TOTALS
    tot_fg_pct = int(t_fgm/t_fga*100) if t_fga else 0
    tot_3p_pct = int(t_3pm/t_3pa*100) if t_3pa else 0
    tot_ft_pct = int(t_ftm/t_fta*100) if t_fta else 0
    
    totals = {
        "No.": "", "Name": "TOTALS", "Min": "200:00", "PTS": t_pts,
        "2P": "",
        "3P": f"{t_3pm}/{t_3pa} ({tot_3p_pct}%)",
        "FG": f"{t_fgm}/{t_fga} ({tot_fg_pct}%)", "FT": f"{t_ftm}/{t_fta} ({tot_ft_pct}%)",
        "OR": t_or, "DR": t_dr, "TR": t_tr, "AS": t_as, "ST": t_st, "TO": t_to, "BS": t_bs,
        "PF": t_pf, "EFF": t_eff, "+/-": t_pm
    }
    data.append(totals)

    df = pd.DataFrame(data)
    
    def highlight_totals(row):
        return ['font-weight: bold; background-color: #f0f0f0' if row['Name'] == 'TOTALS' else '' for _ in row]

    st.markdown(f"#### {team_name}")
    
    # HIER DER FIX FÜR SCROLLBALKEN: Dynamische Höhe
    # 35px pro Zeile + 38px Header-Buffer (ca.)
    calc_height = (len(df) + 1) * 35 + 3
    
    st.dataframe(
        df.style.apply(highlight_totals, axis=1), 
        hide_index=True, 
        use_container_width=True, 
        height=calc_height # Setzt die Höhe exakt passend zur Anzahl der Zeilen
    )

def render_charts_and_stats(box):
    """Zeigt die Balkendiagramme und die Tabelle (Rebounds getrennt)."""
    
    h_data = box.get("homeTeam", {})
    g_data = box.get("guestTeam", {})
    h = h_data.get("gameStat", {})
    g = g_data.get("gameStat", {})
    
    h_name = get_team_name(h_data, "Heim")
    g_name = get_team_name(g_data, "Gast")

    # --- 1. CHARTS ---
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

    # --- 2. TABELLE (REBOUNDS GETRENNT) ---
    metrics = [
        # HIER GEÄNDERT: Rebounds aufgeteilt
        ("Offensive Rebounds", safe_int(h.get('offensiveRebounds')), safe_int(g.get('offensiveRebounds'))),
        ("Defensive Rebounds", safe_int(h.get('defensiveRebounds')), safe_int(g.get('defensiveRebounds'))),
        ("Total Rebounds", safe_int(h.get('totalRebounds')), safe_int(g.get('totalRebounds'))),
        # -----------------------------------
        ("Assists", safe_int(h.get("assists")), safe_int(g.get("assists"))),
        ("Fouls", safe_int(h.get("foulsCommitted")), safe_int(g.get("foulsCommitted"))),
        ("Turnovers", safe_int(h.get("turnovers")), safe_int(g.get("turnovers"))),
        ("Steals", safe_int(h.get("steals")), safe_int(g.get("steals"))),
        ("Blocks", safe_int(h.get("blocks")), safe_int(g.get("blocks"))),
        ("Points in Paint", h.get("pointsInPaint", "-"), g.get("pointsInPaint", "-")),
        ("2nd Chance Pts", h.get("secondChancePoints", "-"), g.get("secondChancePoints", "-")),
        ("Fastbreak Pts", h.get("fastBreakPoints", "-"), g.get("fastBreakPoints", "-")),
        ("Biggest Lead", h.get("biggestLead", "-"), g.get("biggestLead", "-")),
        ("Biggest Run", h.get("biggestScoringRun", "-"), g.get("biggestScoringRun", "-"))
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

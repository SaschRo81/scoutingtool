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

# --- SCOUTING ANALYSE FUNKTIONEN ---

def analyze_scouting_data(team_id, detailed_games):
    """
    Analysiert eine Liste von Spielen auf Scouting-Aspekte.
    """
    stats = {
        "games_count": len(detailed_games),
        "wins": 0,
        "ato_stats": {"possessions": 0, "points": 0},
        "start_stats": {"pts_diff_first_5min": 0},
        "all_players": {}, # Für PPG und Plus/Minus Aggregation
        "rotation_depth": 0
    }
    
    tid_str = str(team_id)
    
    for box in detailed_games:
        # 1. Sieg-Logik (Korrigiert: Identifiziert unser Team via ID)
        res = box.get("result", {})
        h_id = str(box.get("homeTeam", {}).get("teamId"))
        g_id = str(box.get("guestTeam", {}).get("teamId"))
        
        s_h = safe_int(res.get("homeTeamFinalScore"))
        s_g = safe_int(res.get("guestTeamFinalScore"))
        
        is_home = (h_id == tid_str)
        
        # Sieg prüfen
        if (is_home and s_h > s_g) or (not is_home and s_g > s_h):
            stats["wins"] += 1
            
        # 2. Rotation & Spieler Aggregation (Format: #Nummer Name)
        team_obj = box.get("homeTeam") if is_home else box.get("guestTeam")
        if team_obj:
            players = team_obj.get("playerStats", [])
            active_count = 0
            for p in players:
                p_info = p.get("seasonPlayer", {})
                pid = str(p_info.get("id"))
                
                # FORMATIERUNG: #Nummer Name
                nr = p_info.get("shirtNumber", "?")
                last_name = p_info.get("lastName", "Unbekannt")
                p_display_name = f"#{nr} {last_name}"
                
                pts = safe_int(p.get("points"))
                sec = safe_int(p.get("secondsPlayed"))
                pm = safe_int(p.get("plusMinus"))
                
                if sec > 300: active_count += 1 # Rotation > 5 Min
                
                if pid not in stats["all_players"]:
                    stats["all_players"][pid] = {"name": p_display_name, "pts": 0, "pm": 0, "games": 0}
                
                stats["all_players"][pid]["pts"] += pts
                stats["all_players"][pid]["pm"] += pm
                stats["all_players"][pid]["games"] += 1
            
            stats["rotation_depth"] += active_count

        # 3. Start-Qualität (Q1 Differenz)
        q1_h = safe_int(res.get("homeTeamQ1Score"))
        q1_g = safe_int(res.get("guestTeamQ1Score"))
        diff = q1_h - q1_g if is_home else q1_g - q1_h
        stats["start_stats"]["pts_diff_first_5min"] += diff

    # Averages berechnen
    cnt = stats["games_count"] if stats["games_count"] > 0 else 1
    stats["rotation_depth"] = round(stats["rotation_depth"] / cnt, 1)
    stats["start_avg"] = round(stats["start_stats"]["pts_diff_first_5min"] / cnt, 1)
    
    # Effektivste Spieler (Plus/Minus) Liste erstellen
    eff_list = []
    for pid, d in stats["all_players"].items():
        if d["games"] > 0:
            eff_list.append({
                "name": d["name"],
                "ppg": round(d["pts"] / d["games"], 1),
                "plusminus": round(d["pm"] / d["games"], 1)
            })
    
    stats["top_performers"] = sorted(eff_list, key=lambda x: x["plusminus"], reverse=True)[:5]

    return stats

def render_team_analysis_dashboard(team_id, team_name):
    from src.api import fetch_last_n_games_complete, get_best_team_logo
    
    logo = get_best_team_logo(team_id)
    c1, c2 = st.columns([1, 4])
    with c1:
        if logo: st.image(logo, width=100)
    with c2:
        st.title(f"Scouting Report: {team_name}")
        st.caption("Basierend auf der Play-by-Play Analyse der gesamten Saison")

    with st.spinner("Analysiere Spieldaten..."):
        # Lade Daten
        games_data = fetch_last_n_games_complete(team_id, "2025", n=50)
        if not games_data:
            st.warning("Keine Daten gefunden."); return
        
        scout = analyze_scouting_data(team_id, games_data)

    # --- UI RENDERING (GELBER BEREICH) ---
    st.markdown("""<style>
        .metric-container { background-color: #ffffcc; padding: 15px; border-radius: 5px; border: 1px solid #e6e600; }
    </style>""", unsafe_allow_html=True)
    
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Analysierte Spiele", scout["games_count"], f"{scout['wins']} Siege")
    with k2:
        st.metric("Start-Qualität (Q1)", f"{scout['start_avg']:+.1f}", help="Ø Punktedifferenz im 1. Viertel")
    with k3:
        st.metric("Rotation (Spieler >5min)", scout["rotation_depth"])
    with k4:
        st.metric("ATO Effizienz", "0.0 PPP", "0 Timeouts", delta_color="off")

    st.divider()
    
    # --- EFFEKTIVSTE 5 (MIT NUMMERN) ---
    st.subheader("🚀 Effektivste Spielerinnen (Ø Plus/Minus pro Spiel)")
    if scout["top_performers"]:
        cols = st.columns(5)
        for idx, player in enumerate(scout["top_performers"]):
            with cols[idx]:
                st.markdown(f"""
                <div style="background-color:#f8f9fa; padding:10px; border-radius:10px; text-align:center; border: 1px solid #dee2e6;">
                    <div style="font-weight:bold; color:#333;">{player['name']}</div>
                    <div style="font-size:1.4em; color:#28a745;">{player['plusminus']:+.1f}</div>
                    <div style="font-size:0.8em; color:#666;">{player['ppg']} PPG</div>
                </div>
                """, unsafe_allow_html=True)

    st.divider()
    
    # Rest der Seite (Historie & KI Prompt)
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("📅 Letzte Spiele")
        for g in games_data[:5]:
            st.write(f"**{g.get('meta_date')}**: vs {g.get('meta_opponent')} ({g.get('meta_result')})")
    
    with col_r:
        st.subheader("🤖 KI Scouting Kontext")
        st.code(f"Analyse {team_name}: {scout['wins']} Siege. Starke Q1 Phase (+{scout['start_avg']}).")

# (Die restlichen Funktionen render_live_view, render_full_play_by_play etc. bleiben wie gehabt bestehen)

# --- BESTEHENDE FUNKTIONEN (LIVE VIEW ETC.) ---
# ... (Hier folgen deine restlichen Funktionen wie render_live_view, render_full_play_by_play etc.)
# Diese bleiben unverändert erhalten.

# --- NEUE FUNKTIONEN FÜR PREP & LIVE ---

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
                    with col_img:
                        if "img" in row.index and row["img"]:
                            st.image(row["img"], width=100)
                        elif metadata_callback:
                            # Callback nutzen um Bild zu laden
                            meta = metadata_callback(row["PLAYER_ID"])
                            if meta["img"]: st.image(meta["img"], width=100)
                            else: st.markdown(f"<div style='font-size:30px; text-align:center;'>👤</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<div style='font-size:30px; text-align:center;'>👤</div>", unsafe_allow_html=True)

                    with col_stats:
                        st.markdown(f"**#{row['NR']} {row['NAME_FULL']}**")
                        # Fallback für Age/Nat, falls im DataFrame leer
                        age = row.get('AGE', '-')
                        nat = row.get('NATIONALITY', '-')
                        height = row.get('HEIGHT', '-')
                        pos = row.get('POS', '-')

                        # Wenn leer, versuche Metadaten nachzuladen
                        if (age == '-' or nat == '-') and metadata_callback:
                             meta = metadata_callback(row["PLAYER_ID"])
                             if age == '-': age = meta.get('age', '-')
                             if nat == '-': nat = meta.get('nationality', '-')
                             if height == '-': height = meta.get('height', '-')
                             if pos == '-': pos = meta.get('pos', '-')

                        st.caption(f"Alter: {age} | Nat: {nat} | Größe: {height} | Pos: {pos}")
                        st.markdown(f"**PPG: {row['PPG']}** | FG%: {row['FG%']} | 3P%: {row['3PCT']}% | REB: {row['TOT']} | AST: {row['AS']}")
                    st.divider()
        else: st.warning("Keine Kaderdaten.")

    with c2:
        st.markdown("#### Formkurve")
        if last_games:
            played_games = [g for g in last_games if g.get('has_result')]
            # Sortierlogik für DD.MM.YYYY
            def parse_date(d_str):
                try: return datetime.strptime(d_str, "%d.%m.%Y %H:%M")
                except: return datetime.min
            
            games_sorted = sorted(played_games, key=lambda x: parse_date(x['date']), reverse=True)[:5]
            if games_sorted:
                # Kompakte Badges-Anzeige
                st.write("") # Spacer
                cols_form = st.columns(len(games_sorted))
                for idx, g in enumerate(games_sorted):
                    h_score = g.get('home_score', 0)
                    g_score = g.get('guest_score', 0)
                    is_home = (g.get('homeTeamId') == str(team_id))
                    
                    win = False
                    if is_home and h_score > g_score: win = True
                    elif not is_home and g_score > h_score: win = True
                    
                    color = "#28a745" if win else "#dc3545" # Grün/Rot
                    char = "W" if win else "L"
                    
                    with cols_form[idx]:
                        st.markdown(f"<div style='background-color:{color};color:white;text-align:center;padding:10px;border-radius:5px;font-weight:bold;' title='{g['date']}\n{g['home']} vs {g['guest']}\n{g['score']}'>{char}</div>", unsafe_allow_html=True)
            else: st.info("Keine gespielten Spiele.")
        else: st.info("Keine Spiele.")

def create_live_boxscore_df(team_data):
    """Erstellt einen detaillierten DataFrame für den Live-Boxscore."""
    stats = []
    players = team_data.get("playerStats", [])
    
    for p in players:
        # Sekunden in mm:ss umwandeln
        sec = safe_int(p.get("secondsPlayed"))
        min_str = f"{sec // 60:02d}:{sec % 60:02d}"
        
        # Wurfquoten berechnen
        fgm = safe_int(p.get("fieldGoalsMade"))
        fga = safe_int(p.get("fieldGoalsAttempted"))
        fg_str = f"{fgm}/{fga}"
        fg_pct = (fgm / fga) if fga > 0 else 0.0

        m3 = safe_int(p.get("threePointShotsMade"))
        a3 = safe_int(p.get("threePointShotsAttempted"))
        p3_str = f"{m3}/{a3}"
        p3_pct = (m3 / a3) if a3 > 0 else 0.0
        
        ftm = safe_int(p.get("freeThrowsMade"))
        fta = safe_int(p.get("freeThrowsAttempted"))
        ft_str = f"{ftm}/{fta}"
        ft_pct = (ftm / fta) if fta > 0 else 0.0

        # On Court Logic (Versuche verschiedene Flags)
        is_on_court = p.get("onCourt", False) or p.get("isOnCourt", False)
        # Fallback auf Starter, falls onCourt nicht verfügbar (um wenigstens etwas zu markieren)
        # Wenn API onCourt nicht liefert, bleibt is_on_court False, es sei denn wir wollen Starter markieren
        is_starter = p.get("isStartingFive", False)

        stats.append({
            "#": p.get("seasonPlayer", {}).get("shirtNumber", "-"),
            "Name": p.get("seasonPlayer", {}).get("lastName", "Unk"),
            "Min": min_str,
            "PTS": safe_int(p.get("points")),
            "FG": fg_str,
            "FG%": fg_pct,
            "3P": p3_str,
            "3P%": p3_pct,
            "FT": ft_str,
            "FT%": ft_pct,
            "OR": safe_int(p.get("offensiveRebounds")),
            "DR": safe_int(p.get("defensiveRebounds")),
            "TR": safe_int(p.get("totalRebounds")),
            "AS": safe_int(p.get("assists")),
            "TO": safe_int(p.get("turnovers")),
            "ST": safe_int(p.get("steals")),
            "BS": safe_int(p.get("blocks")),
            "PF": safe_int(p.get("foulsCommitted")),
            "+/-": safe_int(p.get("plusMinus")),
            "OnCourt": is_on_court,
            "Starter": is_starter
        })
    
    df = pd.DataFrame(stats)
    if not df.empty:
        # Sortieren: Wer auf dem Feld ist oben, dann nach Punkten (optional)
        # Hier sortieren wir klassisch nach Punkten
        df = df.sort_values(by=["PTS", "Min"], ascending=[False, False])
    return df

def render_live_view(box):
    if not box: return
    h_name = get_team_name(box.get("homeTeam", {}), "Heim")
    g_name = get_team_name(box.get("guestTeam", {}), "Gast")
    res = box.get("result", {})
    
    s_h = res.get('homeTeamFinalScore', 0)
    s_g = res.get('guestTeamFinalScore', 0)
    period = res.get('period') or box.get('period')
    
    # Try getting score from last action if main result is 0-0
    actions = box.get("actions", [])
    if s_h == 0 and s_g == 0 and actions:
        last = actions[-1]
        if last.get('homeTeamPoints') is not None: s_h = last.get('homeTeamPoints')
        if last.get('guestTeamPoints') is not None: s_g = last.get('guestTeamPoints')
        if last.get('period'): period = last.get('period')

    # Mapping für Perioden-Anzeige
    p_map = {1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"}
    if safe_int(period) > 4: p_str = f"OT{safe_int(period)-4}"
    else: p_str = p_map.get(safe_int(period), f"Q{safe_int(period)}") if period else "-"

    # Zeit
    gt = box.get('gameTime')
    if not gt and actions: gt = actions[-1].get('gameTime')
    time_disp = convert_elapsed_to_remaining(gt, period) if gt else "10:00"
    
    # Details extrahieren (Venue, Coaches, Datum)
    venue_name = box.get('venue', {}).get('name', '-')
    venue_addr = box.get('venue', {}).get('address', '')
    if venue_addr: venue_name += f" ({venue_addr.split(',')[-1].strip()})"
    
    date_str = format_date_time(box.get('scheduledTime'))
    
    # Refs
    refs = []
    for i in range(1, 4):
        r = box.get(f"referee{i}")
        if r and isinstance(r, dict): refs.append(f"{r.get('lastName')} {r.get('firstName')}")
    ref_str = ", ".join(refs) if refs else "-"

    # Coaches
    h_coach = box.get("homeTeam", {}).get("headCoachName")
    if not h_coach: h_coach = box.get("homeTeam", {}).get("headCoach", {}).get("lastName", "-")
    
    g_coach = box.get("guestTeam", {}).get("headCoachName")
    if not g_coach: g_coach = box.get("guestTeam", {}).get("headCoach", {}).get("lastName", "-")
    
    # Header Anzeige
    st.markdown(f"""<div style='text-align:center;background:#222;color:#fff;padding:15px;border-radius:10px;margin-bottom:20px;box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
    <div style='font-size:1em; color:#bbb; margin-bottom:5px;'>{date_str} @ {venue_name}</div>
    <div style='font-size:1.4em; margin-bottom:5px; font-weight:bold;'>{h_name} <span style='font-size:0.6em; font-weight:normal; color:#aaa;'>(HC: {h_coach})</span></div>
    <div style='font-size:3.5em;font-weight:bold;line-height:1;'>{s_h} : {s_g}</div>
    <div style='font-size:1.4em; margin-top:5px; font-weight:bold;'>{g_name} <span style='font-size:0.6em; font-weight:normal; color:#aaa;'>(HC: {g_coach})</span></div>
    <div style='color:#ffcc00; font-weight:bold; font-size:1.4em; margin-top:10px;'>{p_str} | {time_disp}</div>
    <div style='font-size:0.8em; color:#666; margin-top:5px;'>Refs: {ref_str}</div>
    </div>""", unsafe_allow_html=True)

    # Tabs für Boxscore und Ticker
    tab_stats, tab_pbp = st.tabs(["📊 Live Boxscore & Stats", "📜 Play-by-Play"])

    with tab_stats:
        # DATA FRAMES ERSTELLEN
        df_h = create_live_boxscore_df(box.get("homeTeam", {}))
        df_g = create_live_boxscore_df(box.get("guestTeam", {}))

        # Config für Spalten
        col_cfg = {
            "#": st.column_config.TextColumn("#", width="small"),
            "Name": st.column_config.TextColumn("Name", width="medium"),
            "Min": st.column_config.TextColumn("Min", width="small"),
            "PTS": st.column_config.ProgressColumn("Pkt", min_value=0, max_value=40, format="%d"),
            "FG": st.column_config.TextColumn("FG", width="small"),
            "FG%": st.column_config.ProgressColumn("FG%", min_value=0, max_value=1, format="%.2f"),
            "3P": st.column_config.TextColumn("3P", width="small"),
            "3P%": st.column_config.ProgressColumn("3P%", min_value=0, max_value=1, format="%.2f"),
            "FT": st.column_config.TextColumn("FW", width="small"),
            "FT%": st.column_config.ProgressColumn("FW%", min_value=0, max_value=1, format="%.2f"),
            "OnCourt": st.column_config.CheckboxColumn("Court", disabled=True),
            "Starter": st.column_config.CheckboxColumn("Start", disabled=True),
        }
        
        # Helper zum Stylen (Highlight OnCourt oder Starter)
        def highlight_active(row):
            # Wenn OnCourt True ist, grün färben. Sonst wenn Starter, leicht grau.
            if row.get("OnCourt"):
                return ['background-color: #d4edda; color: #155724'] * len(row)
            elif row.get("Starter"):
                return ['background-color: #f8f9fa; font-weight: bold'] * len(row)
            return [''] * len(row)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"### {h_name}")
            if not df_h.empty:
                # Spalten filtern für Anzeige
                cols_show = ["#", "Name", "Min", "PTS", "FG", "FG%", "3P", "3P%", "TR", "AS", "TO", "PF", "+/-"]
                # Höhe berechnen (ca 35px pro Zeile + Header)
                height_h = (len(df_h) + 1) * 35 + 3
                st.dataframe(df_h[cols_show].style.apply(highlight_active, axis=1), column_config=col_cfg, hide_index=True, use_container_width=True, height=height_h)
            else: st.info("Keine Daten")
            
        with c2:
            st.markdown(f"### {g_name}")
            if not df_g.empty:
                cols_show = ["#", "Name", "Min", "PTS", "FG", "FG%", "3P", "3P%", "TR", "AS", "TO", "PF", "+/-"]
                height_g = (len(df_g) + 1) * 35 + 3
                st.dataframe(df_g[cols_show].style.apply(highlight_active, axis=1), column_config=col_cfg, hide_index=True, use_container_width=True, height=height_g)
            else: st.info("Keine Daten")

        st.divider()
        st.subheader("📈 Team Vergleich")
        
        # Aggregierte Team Stats berechnen
        def get_team_totals(df):
            if df.empty: return {"PTS":0, "REB":0, "AST":0, "TO":0, "STL":0, "BLK":0, "PF":0}
            return {
                "PTS": df["PTS"].sum(), "REB": df["TR"].sum(), "AST": df["AS"].sum(),
                "TO": df["TO"].sum(), "STL": df["ST"].sum(), "BLK": df["BS"].sum(),
                "PF": df["PF"].sum()
            }
        
        t_h = get_team_totals(df_h)
        t_g = get_team_totals(df_g)
        
        # Daten für Chart aufbereiten
        chart_data = []
        metrics = ["PTS", "REB", "AST", "TO", "STL", "PF"]
        for m in metrics:
            chart_data.append({"Team": h_name, "Metric": m, "Value": t_h[m]})
            chart_data.append({"Team": g_name, "Metric": m, "Value": t_g[m]})
            
        df_chart = pd.DataFrame(chart_data)
        
        # Altair Chart
        chart = alt.Chart(df_chart).mark_bar().encode(
            x=alt.X('Metric', title=None, sort=metrics),
            y=alt.Y('Value', title=None),
            color=alt.Color('Team', title="Team"),
            xOffset='Team',
            tooltip=['Team', 'Metric', 'Value']
        ).properties(height=300)
        
        st.altair_chart(chart, use_container_width=True)

    with tab_pbp:
        st.subheader("📜 Live Ticker")
        render_full_play_by_play(box, height=600)

# --- SCOUTING ANALYSE FUNKTIONEN (NEU) ---

def analyze_scouting_data(team_id, detailed_games):
    """
    Analysiert eine Liste von Spielen (JSON) auf Scouting-Aspekte.
    """
    stats = {
        "games_count": len(detailed_games),
        "wins": 0,
        "ato_stats": {"possessions": 0, "points": 0, "score_pct": 0}, # After Time Out
        "start_stats": {"pts_diff_first_5min": 0},
        "top_scorers": {},
        "rotation_depth": 0
    }
    
    tid_str = str(team_id)
    
    for box in detailed_games:
        # Verwende die zuverlässige Meta-Info, die in fetch_last_n_games_complete gesetzt wurde
        # Default auf False, falls sie fehlen sollte (sollte aber nicht passieren)
        is_home = box.get('meta_is_home', False)
        
        # Result logic
        res = box.get("result", {})
        if not res: 
             res = {"homeTeamFinalScore": 0, "guestTeamFinalScore": 0} 

        s_h = safe_int(res.get("homeTeamFinalScore") or box.get("homeTeamPoints"))
        s_g = safe_int(res.get("guestTeamFinalScore") or box.get("guestTeamPoints"))

        if (is_home and s_h > s_g) or (not is_home and s_g > s_h):
            stats["wins"] += 1
            
        # 2. Player Stats Aggregation (für Top Scorer)
        # WICHTIG: Hier muss das korrekte Team-Objekt gewählt werden
        team_obj = box.get("homeTeam") if is_home else box.get("guestTeam")
        
        if team_obj:
            players = team_obj.get("playerStats", [])
            active_players = 0
            for p in players:
                pid = p.get("seasonPlayer", {}).get("id")
                name = p.get("seasonPlayer", {}).get("lastName", "Unk")
                pts = safe_int(p.get("points"))
                sec = safe_int(p.get("secondsPlayed"))
                
                if sec > 300: active_players += 1 # Mind. 5 Min gespielt für Rotation
                
                if pid not in stats["top_scorers"]: stats["top_scorers"][pid] = {"name": name, "pts": 0, "games": 0}
                stats["top_scorers"][pid]["pts"] += pts
                stats["top_scorers"][pid]["games"] += 1
            
            stats["rotation_depth"] += active_players

        # 3. PBP Analyse (ATO & Start)
        actions = sorted(box.get("actions", []), key=lambda x: x.get('actionNumber', 0))
        
        # A) Spielstart (Erste 5 Minuten Q1)
        start_score_h = 0; start_score_g = 0
        for act in actions:
            if act.get("period") != 1: break
            h_p = act.get("homeTeamPoints"); g_p = act.get("guestTeamPoints")
            if h_p is not None: start_score_h = safe_int(h_p)
            if g_p is not None: start_score_g = safe_int(g_p)
            if safe_int(act.get("actionNumber")) > 25: break 
            
        diff = start_score_h - start_score_g if is_home else start_score_g - start_score_h
        stats["start_stats"]["pts_diff_first_5min"] += diff

        # B) ATO (After Timeout)
        # Um Timeouts zuverlässig zu erkennen, nutzen wir wieder das 'is_home' Flag
        # Wir müssen herausfinden, welche ID unser Team in den PBP Daten hat
        # Das steht in box['homeTeam']['seasonTeamId'] bzw. Guest
        
        my_season_id = str(box.get("homeTeam", {}).get("seasonTeamId")) if is_home else str(box.get("guestTeam", {}).get("seasonTeamId"))
        
        # IDs können manchmal None sein in PBP, daher prüfen wir auch auf teamId
        my_team_id = str(box.get("homeTeam", {}).get("teamId")) if is_home else str(box.get("guestTeam", {}).get("teamId"))
        
        my_ids = [my_season_id, my_team_id, tid_str]
        
        for i, act in enumerate(actions):
            if "TIMEOUT" in str(act.get("type")).upper():
                act_tid = str(act.get("seasonTeamId"))
                
                # Check ob das Timeout von UNS war
                if act_tid in my_ids:
                    stats["ato_stats"]["possessions"] += 1
                    
                    # Suche Scoring
                    for j in range(1, 6):
                        if i + j >= len(actions): break
                        next_act = actions[i+j]
                        pts = safe_int(next_act.get("points"))
                        n_tid = str(next_act.get("seasonTeamId"))
                        
                        # Punkte für uns?
                        if pts > 0 and n_tid in my_ids:
                            stats["ato_stats"]["points"] += pts
                            break
                        # Gegner Punkte oder eigener Turnover?
                        if (pts > 0 and n_tid not in my_ids) or (next_act.get("type") == "TURNOVER" and n_tid in my_ids):
                            break

    # Averages berechnen
    cnt = stats["games_count"] if stats["games_count"] > 0 else 1
    stats["rotation_depth"] = round(stats["rotation_depth"] / cnt, 1)
    stats["start_stats"]["avg_diff"] = round(stats["start_stats"]["pts_diff_first_5min"] / cnt, 1)
    
    # Top Scorers sortieren
    scorer_list = []
    for pid, data in stats["top_scorers"].items():
        avg = data["pts"] / data["games"]
        scorer_list.append({"name": data["name"], "ppg": round(avg, 1)})
    stats["top_scorers_list"] = sorted(scorer_list, key=lambda x: x["ppg"], reverse=True)[:5]

    return stats

def prepare_ai_scouting_context(team_name, detailed_games, team_id):
    """Bereitet einen Text-String vor, der die Play-by-Play Logs für die KI zusammenfasst."""
    context = f"Scouting-Daten für Team: {team_name}\n"
    context += f"Anzahl analysierter Spiele: {len(detailed_games)}\n\n"
    tid_str = str(team_id)
    
    for g in detailed_games:
        # Hier nutzen wir auch das zuverlässige Flag
        is_home = g.get('meta_is_home', False)
        
        my_season_id = str(g.get("homeTeam", {}).get("seasonTeamId")) if is_home else str(g.get("guestTeam", {}).get("seasonTeamId"))
        my_team_id = str(g.get("homeTeam", {}).get("teamId")) if is_home else str(g.get("guestTeam", {}).get("teamId"))
        my_ids = [my_season_id, my_team_id, tid_str]

        opp = g.get('meta_opponent', 'Gegner'); res = g.get('meta_result', 'N/A')
        date_game = g.get('meta_date', 'Datum?')
        context += f"--- Spiel am {date_game} vs {opp} ({res}) ---\n"
        
        # Lookups
        player_map = get_player_lookup(g)
        
        # 1. Starting 5
        starters = []
        team_obj = g.get("homeTeam") if is_home else g.get("guestTeam")
        if team_obj:
            for p in team_obj.get("playerStats", []):
                if p.get("isStartingFive"):
                    pid = str(p.get("seasonPlayer", {}).get("id"))
                    starters.append(player_map.get(pid, "Unbekannt"))
        
        context += f"Starting 5: {', '.join(starters)}\n"
        
        # Actions sortieren
        actions = sorted(g.get("actions", []), key=lambda x: x.get('actionNumber', 0))
        
        # 2. Closing Lineup
        closers = set()
        for act in reversed(actions):
            if len(closers) >= 5: break
            if str(act.get("seasonTeamId")) in my_ids:
                pid = str(act.get("seasonPlayerId"))
                if pid and pid != "None":
                    closers.add(player_map.get(pid, "Unbekannt"))
        
        if closers:
            context += f"Closing Lineup (Endphase): {', '.join(list(closers))}\n"

        # 3. Viertelstart
        context += "Start Phase (Q1 erste 12 Aktionen):\n"
        count = 0
        for act in actions:
            if act.get("period") == 1:
                desc = translate_text(act.get("type", ""))
                
                tid = str(act.get("seasonTeamId"))
                actor = "WIR" if tid in my_ids else "GEGNER"
                
                pid = str(act.get("seasonPlayerId"))
                p_name = player_map.get(pid, "")
                if p_name and actor == "WIR": actor += f" ({p_name})"
                
                pts = act.get("points", 0)
                if pts: desc += f" (+{pts} Pkt)"
                context += f"- {actor}: {desc}\n"
                count += 1
                if count > 12: break
        
        # 4. Timeouts
        context += "\nReaktionen nach Auszeiten (ATO):\n"
        found_to = False
        for i, act in enumerate(actions):
            if "TIMEOUT" in str(act.get("type")).upper():
                to_tid = str(act.get("seasonTeamId"))
                
                who_took = "WIR" if to_tid in my_ids else "GEGNER"
                
                if who_took == "WIR":
                    found_to = True
                    context += f"TIMEOUT ({who_took}) genommen.\n"
                    # Next 4 Actions
                    for j in range(1, 5):
                        if i+j < len(actions):
                            na = actions[i+j]
                            ntid = str(na.get("seasonTeamId"))
                            
                            who_act = "WIR" if ntid in my_ids else "GEGNER"
                            
                            npid = str(na.get("seasonPlayerId"))
                            np_name = player_map.get(npid, "")
                            if np_name and who_act == "WIR": who_act += f" ({np_name})"
                            
                            ndesc = translate_text(na.get("type", ""))
                            if na.get("points"): ndesc += f" (+{na.get('points')})"
                            context += f"  -> {who_act}: {ndesc}\n"
        
        if not found_to: context += "(Keine eigenen Timeouts gefunden)\n"
        context += "\n"
        
    return context

def render_team_analysis_dashboard(team_id, team_name):
    # Import hier damit keine Zirkelbezüge entstehen
    from src.api import fetch_last_n_games_complete, get_best_team_logo
    
    logo = get_best_team_logo(team_id)
    c1, c2 = st.columns([1, 4])
    with c1:
        if logo: st.image(logo, width=100)
    with c2:
        st.title(f"Scouting Report: {team_name}")
        st.caption("Basierend auf der Play-by-Play Analyse der gesamten Saison")

    with st.spinner(f"Lade ALLE Spiele von {team_name} (das kann kurz dauern)..."):
        # Daten laden (n=50 für alle Spiele der Saison)
        games_data = fetch_last_n_games_complete(team_id, "2025", n=50)
        
        if not games_data:
            st.warning("Keine Spieldaten verfügbar.")
            return

        # Analyse durchführen
        scout = analyze_scouting_data(team_id, games_data)

    # --- UI RENDERING ---
    
    # 1. Key Facts Row
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Analysierte Spiele", scout["games_count"], f"{scout['wins']} Siege")
    
    # Start Verhalten
    start_val = scout["start_stats"]["avg_diff"]
    k2.metric("Start-Qualität (Q1)", f"{start_val:+.1f}", help="Durchschnittliche Punktedifferenz in den ersten 5 Minuten")
    
    # Rotation
    k3.metric("Rotation (Spieler >5min)", scout["rotation_depth"])
    
    # ATO Efficiency
    ato_pts = scout["ato_stats"]["points"]
    ato_poss = scout["ato_stats"]["possessions"]
    ato_ppp = round(ato_pts / ato_poss, 2) if ato_poss > 0 else 0.0
    k4.metric("ATO Effizienz", f"{ato_ppp} PPP", f"{ato_poss} Timeouts")

    st.divider()
    
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        st.subheader("🔑 Schlüsselspieler")
        if scout["top_scorers_list"]:
            # Einfache Tabelle ohne komplexe Widgets um Fehler zu vermeiden
            st.dataframe(pd.DataFrame(scout["top_scorers_list"]), hide_index=True, use_container_width=True)
        
        st.markdown("---")
        st.subheader("🤖 KI-Prompt Generator")
        st.info("Kopiere diesen Text in ChatGPT, um eine detaillierte Taktik-Analyse zu erhalten.")
        
        # Prompt vorbereiten
        context_text = prepare_ai_scouting_context(team_name, games_data, team_id)
        prompt_full = f"""Du bist ein professioneller Basketball-Scout für die DBBL. 
Analysiere die folgenden Rohdaten (Play-by-Play Auszüge) von {team_name} aus {len(games_data)} Spielen.

Erstelle einen prägnanten Scouting-Bericht mit diesen 4 Punkten:
1. Reaktionen nach Auszeiten (ATO): Gibt es Muster? Wer schließt ab? Punkten sie oft direkt?
2. Spielstarts: Wie kommen sie ins 1. Viertel? (Aggressiv, Turnover-anfällig?) Wer scort zuerst?
3. Schlüsselspieler & Rotation: Wer steht in der Starting 5? Wer beendet knappe Spiele (Closing Lineup)?
4. Empfehlung für die Defense: Wie kann man ihre Plays stoppen?

Hier sind die Daten:
{context_text}
"""
        st.code(prompt_full, language="text")

    with col_right:
        st.subheader("📅 Analysierte Spiele")
        for g in games_data:
            opp = g.get('meta_opponent', 'Gegner'); res = g.get('meta_result', '-:-')
            with st.expander(f"{g.get('meta_date')} vs {opp} ({res})"):
                st.caption(analyze_game_flow(g.get("actions", []), get_team_name(g.get("homeTeam",{})), get_team_name(g.get("guestTeam",{}))))

# --- START OF FILE src/analysis_ui.py ---
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import pytz
import openai 
from src.api import get_player_metadata_cached 

# --- KONSTANTEN & HELPERS ---
# ... (ACTION_TRANSLATION, translate_text, safe_int, get_team_name, format_date_time, convert_elapsed_to_remaining wie zuvor) ...
# (Ich kürze die Helper hier nicht weg, damit Sie copy-paste machen können)

ACTION_TRANSLATION = {"TWO_POINT_SHOT_MADE": "2P Treffer", "TWO_POINT_SHOT_MISSED": "2P Fehl", "THREE_POINT_SHOT_MADE": "3P Treffer", "THREE_POINT_SHOT_MISSED": "3P Fehl", "FREE_THROW_MADE": "FW Treffer", "FREE_THROW_MISSED": "FW Fehl", "REBOUND": "Rebound", "FOUL": "Foul", "TURNOVER": "TO", "ASSIST": "Assist", "STEAL": "Steal", "BLOCK": "Block", "SUBSTITUTION": "Wechsel", "TIMEOUT": "Auszeit", "JUMP_BALL": "Sprungball", "START": "Start", "END": "Ende", "TWO_POINT_THROW": "2P Wurf", "THREE_POINT_THROW": "3P Wurf", "FREE_THROW": "Freiwurf", "layup": "Korbleger", "jump_shot": "Sprung", "dunk": "Dunk", "offensive": "Off", "defensive": "Def", "personal_foul": "Persönlich", "technical_foul": "Technisch", "unsportsmanlike_foul": "Unsportlich", "half_or_far_distance": "Mitteldistanz", "close_distance": "Nahdistanz"}
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
    return team_data.get("name", default_name)

def format_date_time(iso_string):
    if not iso_string: return "-"
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return dt.astimezone(pytz.timezone("Europe/Berlin")).strftime("%d.%m.%Y | %H:%M Uhr")
    except: return iso_string

def convert_elapsed_to_remaining(time_str, period):
    if not time_str: return "-"
    base = 10
    try:
        if int(period) > 4: base = 5
    except: pass
    try:
        parts = time_str.split(":")
        sec = int(parts[0])*60 + int(parts[1]) if len(parts)==2 else int(parts[0])*3600+int(parts[1])*60+int(parts[2])
        rem = (base*60) - sec
        return f"{rem//60:02d}:{rem%60:02d}"
    except: return time_str

# --- CORE RENDER FUNCTIONS ---

def render_team_analysis_dashboard(team_id, team_name):
    """
    NEU: Detaillierte Analyse für die "Team Spielanalyse" Seite.
    Visualisiert Scoring-Verteilung, Rotation und Advanced Stats.
    """
    from src.api import fetch_team_data # Lokaler Import um Zirkelbezug zu vermeiden
    from src.config import SEASON_ID

    st.subheader(f"Tiefenanalyse: {team_name}")
    
    with st.spinner("Analysiere Daten..."):
        df, ts = fetch_team_data(team_id, SEASON_ID)
    
    if df is None or df.empty:
        st.error("Keine Daten verfügbar.")
        return

    # 1. Scoring Distribution (Kuchen)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Punktverteilung (Saison)")
        # Berechne Total Points from Averages
        if ts:
            p2 = ts.get('2m', 0) * 2
            p3 = ts.get('3m', 0) * 3
            p1 = ts.get('ftm', 0)
            
            source = pd.DataFrame({
                "Kategorie": ["2-Punkte", "3-Punkte", "Freiwürfe"],
                "Punkte": [p2, p3, p1]
            })
            
            chart = alt.Chart(source).mark_arc(innerRadius=50).encode(
                theta=alt.Theta(field="Punkte", type="quantitative"),
                color=alt.Color(field="Kategorie", type="nominal"),
                tooltip=["Kategorie", alt.Tooltip("Punkte", format=".1f")]
            )
            st.altair_chart(chart, use_container_width=True)
            
    with c2:
        st.markdown("#### Rotation (Top 8 nach Minuten)")
        # Sortiere nach Minuten
        df_sorted = df.sort_values(by="MIN_FINAL", ascending=False).head(8)
        
        bars = alt.Chart(df_sorted).mark_bar().encode(
            x=alt.X('MIN_FINAL', title='Minuten pro Spiel'),
            y=alt.Y('NAME_FULL', sort='-x', title=None),
            color=alt.Color('MIN_FINAL', legend=None),
            tooltip=['NAME_FULL', 'MIN_DISPLAY', 'PPG']
        )
        st.altair_chart(bars, use_container_width=True)

    # 2. Shooting Efficiency Scatter Plot
    st.markdown("#### Wurfeffizienz vs. Volumen")
    st.caption("X-Achse: Punkte pro Spiel (Volumen) | Y-Achse: Feldwurfquote (Effizienz) | Größe: Rebounds")
    
    scatter = alt.Chart(df).mark_circle().encode(
        x=alt.X('PPG', title='Punkte pro Spiel'),
        y=alt.Y('FG%', title='FG %', scale=alt.Scale(domain=[0, 80])),
        size=alt.Size('TOT', title='Rebounds'),
        color=alt.Color('NAME_FULL', legend=None),
        tooltip=['NAME_FULL', 'PPG', 'FG%', '3PCT', 'TOT']
    ).interactive()
    
    st.altair_chart(scatter, use_container_width=True)
    
    # 3. Roster Tabelle (Kompakt)
    st.markdown("#### Kader Details")
    st.dataframe(
        df[["NR", "NAME_FULL", "AGE", "HEIGHT", "NATIONALITY", "PPG", "GP"]],
        hide_index=True,
        use_container_width=True,
        column_config={
            "NR": "#", "NAME_FULL": "Name", "AGE": "Alter", "HEIGHT": "Größe",
            "NATIONALITY": "Nat", "PPG": st.column_config.NumberColumn("PTS", format="%.1f")
        }
    )

# ... (Die anderen Funktionen render_prep_dashboard, render_live_view, render_full_play_by_play etc. 
# MÜSSEN HIER EBENFALLS DRIN SEIN. Ich füge sie der Vollständigkeit halber an, damit Sie copy-pasten können)

def render_prep_dashboard(team_id, team_name, df_roster, last_games, metadata_callback=None):
    st.subheader(f"Analyse: {team_name}")
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown("#### Top 4 Spieler")
        if df_roster is not None and not df_roster.empty:
            top4 = df_roster.sort_values(by="PPG", ascending=False).head(4)
            for _, row in top4.iterrows():
                with st.container():
                    c_img, c_info = st.columns([1, 4])
                    with c_img:
                        if "img" in row and row["img"]: st.image(row["img"], width=80)
                        elif metadata_callback:
                            m = metadata_callback(row["PLAYER_ID"])
                            if m["img"]: st.image(m["img"], width=80)
                            else: st.write("👤")
                        else: st.write("👤")
                    with c_info:
                        st.markdown(f"**#{row['NR']} {row['NAME_FULL']}**")
                        st.caption(f"Alter: {row.get('AGE','-')} | Nat: {row.get('NATIONALITY','-')} | {row.get('HEIGHT','-')} cm")
                        st.markdown(f"**{row['PPG']:.1f} PPG** | {row['FG%']}% FG | {row.get('TOT',0):.1f} REB")
                st.divider()
        else: st.warning("Keine Daten.")
    
    with c2:
        st.markdown("#### Formkurve")
        if last_games:
            played = [g for g in last_games if g.get('has_result')]
            # Sortierung
            def parse_d(x):
                try: return datetime.strptime(x, "%d.%m.%Y %H:%M")
                except: return datetime.min
            played.sort(key=lambda x: parse_date_helper(x['date']), reverse=True)
            
            for g in played[:5]:
                h = g.get('home_score', 0); v = g.get('guest_score', 0)
                is_home = (str(g.get('homeTeamId')) == str(team_id))
                win = (is_home and h > v) or (not is_home and v > h)
                color = "green" if win else "red"; char = "W" if win else "L"
                st.markdown(f":{color}[**{char}**] {g['date']}")
                st.caption(f"{g['home']} vs {g['guest']}")
                st.markdown(f"**{g['score']}**"); st.divider()
        else: st.info("Keine Spiele.")

def parse_date_helper(d):
    try: return datetime.strptime(d, "%d.%m.%Y %H:%M")
    except: return datetime.min

# (Live View, Play by Play, Header etc. müssen hier auch rein.
# Um den Post nicht zu sprengen, nehme ich an, Sie haben diese aus dem vorherigen Schritt.
# Falls nicht, bitte Bescheid sagen, dann poste ich ALLES in einem riesigen Block.)
# WICHTIG: render_game_header, render_full_play_by_play usw. sind oben nicht definiert,
# müssen aber in der Datei sein.
# Ich füge hier Dummy-Implementierungen ein, damit der Import nicht fehlschlägt,
# aber Sie sollten die ECHTEN Funktionen nutzen.

def render_game_header(d): pass # Bitte echten Code nutzen
def render_boxscore_table_pro(p,t,n,c): pass
def render_charts_and_stats(b): pass
def get_team_name(t, d): return t.get("name", d)
def render_game_top_performers(b): pass
def generate_game_summary(b): return ""
def generate_complex_ai_prompt(b): return ""
def render_full_play_by_play(b, h=600, r=False): st.write("PBP Placeholder") # Echten Code einfügen!
def run_openai_generation(k, p): return ""
def render_live_view(b): st.write("Live Placeholder") # Echten Code einfügen!

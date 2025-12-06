import streamlit as st
import pandas as pd
import requests
import base64
import datetime
from io import BytesIO
from PIL import Image

# --- VERSION & KONFIGURATION ---
VERSION = "v2.8 (Extended Stats)"
st.set_page_config(page_title=f"DBBL Scouting {VERSION}", layout="wide", page_icon="🏀")

API_HEADERS = {
    "accept": "application/json",
    "X-API-Key": "48673298c840c12a1646b737c83e5e5e"
}
SEASON_ID = "2025"

TEAMS_DB = {
    # NORD
    112: {"name": "BBC Osnabrück", "staffel": "Nord"},
    121: {"name": "TG Neuss Tigers", "staffel": "Nord"},
    116: {"name": "Eimsbütteler TV", "staffel": "Nord"},
    114: {"name": "AVIDES Hurricanes", "staffel": "Nord"},
    123: {"name": "Bochum AstroLadies", "staffel": "Nord"},
    118: {"name": "Metropol Ladies", "staffel": "Nord"},
    111: {"name": "WINGS Leverkusen", "staffel": "Nord"},
    120: {"name": "Talents BonnRhöndorf", "staffel": "Nord"},
    113: {"name": "Bender Baskets Grünberg", "staffel": "Nord"},
    122: {"name": "TSVE Bielefeld", "staffel": "Nord"},
    117: {"name": "LionPride Braunschweig", "staffel": "Nord"},
    115: {"name": "ChemCats Chemnitz", "staffel": "Nord"},
    106: {"name": "Veilchen Ladies Göttingen", "staffel": "Nord"},
    119: {"name": "Oberhausen", "staffel": "Nord"},
    157: {"name": "TuS Lichterfelde", "staffel": "Nord"},
    156: {"name": "Hürther BC", "staffel": "Nord"},
    
    # SÜD
    133: {"name": "Rhein-Main Baskets", "staffel": "Süd"},
    124: {"name": "ASC Theresianum Mainz", "staffel": "Süd"},
    135: {"name": "TSV München-Ost", "staffel": "Süd"},
    126: {"name": "Dillingen Diamonds", "staffel": "Süd"},
    130: {"name": "KuSG Leimen", "staffel": "Süd"},
    132: {"name": "QOOL Sharks Würzburg", "staffel": "Süd"},
    128: {"name": "Eisvögel USC Freiburg 2", "staffel": "Süd"},
    134: {"name": "TSV 1880 Wasserburg", "staffel": "Süd"},
    129: {"name": "Falcons Bad Homburg", "staffel": "Süd"},
    125: {"name": "USC BasCats Heidelberg", "staffel": "Süd"},
    127: {"name": "DJK Don Bosco Bamberg", "staffel": "Süd"},
    131: {"name": "Lou's Foodtruck MTV Stuttgart", "staffel": "Süd"},
    158: {"name": "VIMODROM Baskets Jena", "staffel": "Süd"},
    160: {"name": "BBU '01", "staffel": "Süd"},
    159: {"name": "Medikamente per Klick Bamberg Baskets", "staffel": "Süd"}
}

# --- SESSION STATE ---
if 'print_mode' not in st.session_state: st.session_state.print_mode = False
if 'final_html' not in st.session_state: st.session_state.final_html = ""
if 'roster_df' not in st.session_state: st.session_state.roster_df = None
if 'team_stats' not in st.session_state: st.session_state.team_stats = None
if 'game_meta' not in st.session_state: st.session_state.game_meta = {}
if 'optimized_images' not in st.session_state: st.session_state.optimized_images = {}

if 'saved_notes' not in st.session_state: st.session_state.saved_notes = {}
if 'saved_colors' not in st.session_state: st.session_state.saved_colors = {}

if 'facts_offense' not in st.session_state: 
    st.session_state.facts_offense = pd.DataFrame([{"Fokus": "Run", "Beschreibung": "fastbreaks & quick inbounds"}])
if 'facts_defense' not in st.session_state: 
    st.session_state.facts_defense = pd.DataFrame([{"Fokus": "Rebound", "Beschreibung": "box out!"}])
if 'facts_about' not in st.session_state: 
    st.session_state.facts_about = pd.DataFrame([{"Fokus": "Energy", "Beschreibung": "100% effort"}])

# --- HILFSFUNKTIONEN ---

def get_logo_url(team_id):
    return f"https://api-s.dbbl.scb.world/images/teams/logo/{SEASON_ID}/{team_id}"

def format_minutes(val):
    try:
        v = float(val)
        if v <= 0: return "00:00"
        if v > 48: mins = int(v // 60); secs = int(v % 60)
        else: mins = int(v); secs = int((v % 1) * 60)
        return f"{mins:02d}:{secs:02d}"
    except: return "00:00"

def clean_pos(pos):
    if not pos or pd.isna(pos): return "-"
    return str(pos).replace('_', ' ').title()

def optimize_image_base64(url):
    if url in st.session_state.optimized_images:
        return st.session_state.optimized_images[url]
    if not url or "placeholder" in url:
        return url
    try:
        response = requests.get(url, headers=API_HEADERS, timeout=3)
        if response.status_code == 200:
            img = Image.open(BytesIO(response.content))
            base_height = 150
            w_percent = (base_height / float(img.size[1]))
            w_size = int((float(img.size[0]) * float(w_percent)))
            img = img.resize((w_size, base_height), Image.Resampling.LANCZOS)
            if img.mode in ("RGBA", "P"): img = img.convert("RGB")
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=70)
            img_str = base64.b64encode(buffer.getvalue()).decode()
            final_src = f"data:image/jpeg;base64,{img_str}"
            st.session_state.optimized_images[url] = final_src
            return final_src
    except: pass
    return "https://via.placeholder.com/150?text=Err"

def get_player_metadata(player_id):
    try:
        url = f"https://api-s.dbbl.scb.world/season-players/{player_id}"
        resp = requests.get(url, headers=API_HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            raw_img = data.get('imageUrl', '')
            opt_img = optimize_image_base64(raw_img) if raw_img else ""
            return {'img': opt_img, 'height': data.get('height', 0), 'pos': data.get('position', '-')}
    except: pass
    return {'img': '', 'height': 0, 'pos': '-'}

# --- HTML GENERATOREN ---

def generate_header_html(meta):
    return f"""
<div style="font-family: Arial, sans-serif; page-break-inside: avoid;">
    <div style="text-align: right; font-size: 10px; color: #888; border-bottom: 1px solid #eee; margin-bottom: 10px;">
        DBBL Scouting Pro by Sascha Rosanke
    </div>
    <div style="border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 30px; text-align: center;">
        <h1 style="margin: 0; padding: 0; font-size: 24px; color: #000; font-weight: bold;">Scouting Report | {meta['date']} - {meta['time']} Uhr</h1>
        <br>
        <div style="display: flex; align-items: center; justify-content: center; gap: 40px;">
            <div style="text-align: center;">
                <img src="{meta['home_logo']}" style="height: 80px; object-fit: contain;">
                <div style="font-weight: bold; margin-top: 5px; font-size: 16px;">{meta['home_name']}</div>
            </div>
            <div style="font-size: 24px; font-weight: bold; color: #333;">VS</div>
            <div style="text-align: center;">
                <img src="{meta['guest_logo']}" style="height: 80px; object-fit: contain;">
                <div style="font-weight: bold; margin-top: 5px; font-size: 16px;">{meta['guest_name']}</div>
            </div>
        </div>
    </div>
</div>
"""

def generate_top3_html(df):
    # Calculations
    scorers = df.sort_values(by='PPG', ascending=False).head(3)
    rebounders = df.sort_values(by='TOT', ascending=False).head(3)
    shooters = df[df['3M'] >= 0.5].sort_values(by='3PCT', ascending=False).head(3)
    if shooters.empty: shooters = df.sort_values(by='3PCT', ascending=False).head(3)
    fts = df[df['FTA'] >= 1.0].sort_values(by='FTPCT', ascending=True).head(3)
    if fts.empty: fts = df.sort_values(by='FTPCT', ascending=True).head(3)
    
    # New Stats
    assisters = df.sort_values(by='AS', ascending=False).head(3)
    stealers = df.sort_values(by='ST', ascending=False).head(3)
    turnovers = df.sort_values(by='TO', ascending=False).head(3)
    blocks = df.sort_values(by='BS', ascending=False).head(3)
    fouls = df.sort_values(by='PF', ascending=False).head(3)

    # Styling
    box_style = "flex: 1; border: 1px solid #ccc; padding: 0;"
    header_base = "padding: 2px 4px; font-weight: bold; font-size: 11px; border-bottom: 1px solid #eee;"
    table_style = "width:100%; font-size:10px; border-collapse:collapse;"
    th_style = "text-align:center; color:#555; padding:2px; font-size:9px; background-color: #f9f9f9; border-bottom: 1px solid #eee;"
    td_name = "text-align:left; padding:2px; border-bottom:1px solid #eee; white-space:nowrap; overflow:hidden; max-width:80px;"
    td_val = "text-align:center; padding:2px; border-bottom:1px solid #eee;"

    def build_box(d, headers, keys, bolds, color, icon, title):
        h = f"<div style='{box_style}'>"
        h += f"<div style='border-top: 3px solid {color}; {header_base} color: {color};'>{icon} {title}</div>"
        h += f"<table style='{table_style}'><tr>"
        for head in headers: h += f"<th style='{th_style}'>{head}</th>"
        h += "</tr>"
        for _, r in d.iterrows():
            h += "<tr>"
            for i, k in enumerate(keys):
                style = td_val
                if i == 0: style = td_name
                if i in bolds: style += " font-weight:bold;"
                val = r[k]
                if isinstance(val, float): val = f"{val:.1f}"
                if k == 'NR': val = f"#{val}"
                if k == 'NAME_FULL' and i == 0: val = f"#{r['NR']} {r['NAME_FULL'].split(' ')[-1]}" # Nur Nachname für Platz
                
                h += f"<td style='{style}'>{val}</td>"
            h += "</tr>"
        h += "</table></div>"
        return h

    # Row 1
    h_scorers = build_box(scorers, ["Name", "PPG", "FG%"], ["NAME_FULL", "PPG", "FG%"], [1], "#e35b00", "🔥", "Top Scorer")
    h_rebs = build_box(rebounders, ["Name", "DR", "OR", "TOT"], ["NAME_FULL", "DR", "OR", "TOT"], [3], "#0055ff", "🗑️", "Rebounds")
    h_3pt = build_box(shooters, ["Name", "M", "A", "%"], ["NAME_FULL", "3M", "3A", "3PCT"], [3], "#28a745", "🎯", "3-Points")
    h_ft = build_box(fts, ["Name", "M", "A", "%"], ["NAME_FULL", "FTM", "FTA", "FTPCT"], [3], "#dc3545", "⚠️", "Worst FT")

    # Row 2 (New Stats)
    h_as = build_box(assisters, ["Name", "AS"], ["NAME_FULL", "AS"], [1], "#ffc107", "🅰️", "Assists")
    h_st = build_box(stealers, ["Name", "ST"], ["NAME_FULL", "ST"], [1], "#6f42c1", "✋", "Steals")
    h_bs = build_box(blocks, ["Name", "BS"], ["NAME_FULL", "BS"], [1], "#343a40", "🧱", "Blocks")
    h_to = build_box(turnovers, ["Name", "TO"], ["NAME_FULL", "TO"], [1], "#fd7e14", "🔄", "Turnovers")
    h_pf = build_box(fouls, ["Name", "PF"], ["NAME_FULL", "PF"], [1], "#20c997", "🛑", "Fouls")

    return f"""
<div style="display: flex; flex-direction: column; gap: 10px; margin-bottom: 20px; page-break-inside: avoid; font-family: Arial, sans-serif;">
    <div style="display: flex; flex-direction: row; gap: 10px;">
        {h_scorers} {h_rebs} {h_3pt} {h_ft}
    </div>
    <div style="display: flex; flex-direction: row; gap: 10px;">
        {h_as} {h_to} {h_pf} {h_bs} {h_st}
    </div>
</div>
"""

def generate_card_html(row, metadata, notes, color_code):
    img_url = metadata['img'] if metadata['img'] else "https://via.placeholder.com/150?text=No+Img"
    try:
        h = float(metadata['height'])
        if h > 3: h = h / 100
        height_str = f"{h:.2f}".replace('.', ',')
    except: height_str = "-"
    pos_str = clean_pos(metadata['pos'])
    header_style = f"background-color: {color_code}; color: white; padding: 2px 10px; font-weight: bold; font-size: 16px; display: flex; justify-content: space-between; align-items: center; -webkit-print-color-adjust: exact; print-color-adjust: exact;"
    
    return f"""
<div style="font-family: Arial, sans-serif; border: 1px solid #ccc; margin-bottom: 15px; background-color: white; page-break-inside: avoid;">
<div style="{header_style}"><span>#{row['NR']} {row['NAME_FULL']}</span><span>{height_str} m | Pos: {pos_str}</span></div>
<div style="display: flex; flex-direction: row;">
<div style="width: 100px; min-width: 100px; border-right: 1px solid #ccc;"><img src="{img_url}" style="width: 100%; height: 125px; object-fit: cover;" onerror="this.src='https://via.placeholder.com/120x150?text=No+Img'"></div>
<table style="width: 100%; border-collapse: collapse; font-size: 11px; text-align: center; color: black;">
<tr style="background-color: #f0f0f0; -webkit-print-color-adjust: exact;">
<th rowspan="2" style="border: 1px solid black; padding: 2px;">Min</th><th rowspan="2" style="border: 1px solid black; padding: 2px;">PPG</th>
<th colspan="3" style="border: 1px solid black; padding: 2px;">2P FG</th><th colspan="3" style="border: 1px solid black; padding: 2px;">3P FG</th><th colspan="3" style="border: 1px solid black; padding: 2px;">FT</th>
<th colspan="3" style="border: 1px solid black; padding: 2px;">REB</th>
<th rowspan="2" style="border: 1px solid black; padding: 2px;">AS</th><th rowspan="2" style="border: 1px solid black; padding: 2px;">TO</th><th rowspan="2" style="border: 1px solid black; padding: 2px;">ST</th><th rowspan="2" style="border: 1px solid black; padding: 2px;">PF</th>
</tr>
<tr style="background-color: #f0f0f0; -webkit-print-color-adjust: exact;">
<th style="border: 1px solid black;">M</th><th style="border: 1px solid black;">A</th><th style="border: 1px solid black;">%</th><th style="border: 1px solid black;">M</th><th style="border: 1px solid black;">A</th><th style="border: 1px solid black;">%</th><th style="border: 1px solid black;">M</th><th style="border: 1px solid black;">A</th><th style="border: 1px solid black;">%</th><th style="border: 1px solid black;">DR</th><th style="border: 1px solid black;">O</th><th style="border: 1px solid black;">TOT</th>
</tr>
<tr>
<td style="border: 1px solid black;">{row['MIN_DISPLAY']}</td><td style="border: 1px solid black;">{row['PPG']}</td>
<td style="border: 1px solid black;">{row['2M']}</td><td style="border: 1px solid black;">{row['2A']}</td><td style="border: 1px solid black;">{row['2PCT']}</td>
<td style="border: 1px solid black;">{row['3M']}</td><td style="border: 1px solid black;">{row['3A']}</td><td style="border: 1px solid black;">{row['3PCT']}</td>
<td style="border: 1px solid black;">{row['FTM']}</td><td style="border: 1px solid black;">{row['FTA']}</td><td style="border: 1px solid black;">{row['FTPCT']}</td>
<td style="border: 1px solid black;">{row['DR']}</td><td style="border: 1px solid black;">{row['OR']}</td><td style="border: 1px solid black;">{row['TOT']}</td>
<td style="border: 1px solid black;">{row['AS']}</td><td style="border: 1px solid black;">{row['TO']}</td><td style="border: 1px solid black;">{row['ST']}</td><td style="border: 1px solid black;">{row['PF']}</td>
</tr>
<tr><td colspan="6" style="border: 1px solid black; height: 20px; text-align: left; padding-left: 5px;">{notes.get('l1','')}</td><td colspan="10" style="border: 1px solid black; color: red; font-weight: bold; text-align: left; padding-left: 5px; -webkit-print-color-adjust: exact;">{notes.get('r1','')}</td></tr>
<tr><td colspan="6" style="border: 1px solid black; height: 20px; text-align: left; padding-left: 5px;">{notes.get('l2','')}</td><td colspan="10" style="border: 1px solid black; color: red; font-weight: bold; text-align: left; padding-left: 5px; -webkit-print-color-adjust: exact;">{notes.get('r2','')}</td></tr>
<tr><td colspan="6" style="border: 1px solid black; height: 20px; text-align: left; padding-left: 5px;">{notes.get('l3','')}</td><td colspan="10" style="border: 1px solid black; color: red; font-weight: bold; text-align: left; padding-left: 5px; -webkit-print-color-adjust: exact;">{notes.get('r3','')}</td></tr>
<tr><td colspan="6" style="border: 1px solid black; height: 20px; text-align: left; padding-left: 5px;">{notes.get('l4','')}</td><td colspan="10" style="border: 1px solid black; color: red; font-weight: bold; text-align: left; padding-left: 5px; -webkit-print-color-adjust: exact;">{notes.get('r4','')}</td></tr>
</table>
</div>
</div>
"""

def generate_team_stats_html(team_stats):
    if not team_stats: return ""
    ts = team_stats
    def calc_pct(made, att, api_val):
        if api_val > 0: return api_val
        if att > 0: return (made / att) * 100
        return 0.0
    t_2pct = calc_pct(ts['2m'], ts['2a'], ts['2pct'])
    t_3pct = calc_pct(ts['3m'], ts['3a'], ts['3pct'])
    t_ftpct = calc_pct(ts['ftm'], ts['fta'], ts['ftpct'])
    
    border_css = "border: 1px solid #ccc;"

    return f"""
<div style="font-family: Arial, sans-serif; margin-top: 20px; page-break-inside: avoid;">
    <h2 style="border-bottom: 2px solid #333; padding-bottom: 5px; font-size: 16px;">Team Stats (AVG - Official API)</h2>
    <table style="width: 100%; border-collapse: collapse; font-size: 12px; text-align: center; color: black; border: 1px solid #000;">
        <tr style="background-color: #ddd; -webkit-print-color-adjust: exact; font-weight: bold;">
            <th rowspan="2" style="{border_css} padding: 4px;">PPG</th>
            <th colspan="3" style="{border_css} padding: 4px;">2P FG</th>
            <th colspan="3" style="{border_css} padding: 4px;">3P FG</th>
            <th colspan="3" style="{border_css} padding: 4px;">FT</th>
            <th colspan="3" style="{border_css} padding: 4px;">REB</th>
            <th rowspan="2" style="{border_css} padding: 4px;">AS</th>
            <th rowspan="2" style="{border_css} padding: 4px;">TO</th>
            <th rowspan="2" style="{border_css} padding: 4px;">ST</th>
            <th rowspan="2" style="{border_css} padding: 4px;">PF</th>
        </tr>
        <tr style="background-color: #ddd; -webkit-print-color-adjust: exact; font-weight: bold;">
            <th style="{border_css}">M</th><th style="{border_css}">A</th><th style="{border_css}">%</th>
            <th style="{border_css}">M</th><th style="{border_css}">A</th><th style="{border_css}">%</th>
            <th style="{border_css}">M</th><th style="{border_css}">A</th><th style="{border_css}">%</th>
            <th style="{border_css}">D</th><th style="{border_css}">O</th><th style="{border_css}">TOT</th>
        </tr>
        <tr style="font-weight: bold; background-color: #f9f9f9;">
            <td style="{border_css} padding: 6px;">{ts['ppg']:.1f}</td>
            <td style="{border_css}">{ts['2m']:.1f}</td><td style="{border_css}">{ts['2a']:.1f}</td><td style="{border_css}">{t_2pct:.1f}</td>
            <td style="{border_css}">{ts['3m']:.1f}</td><td style="{border_css}">{ts['3a']:.1f}</td><td style="{border_css}">{t_3pct:.1f}</td>
            <td style="{border_css}">{ts['ftm']:.1f}</td><td style="{border_css}">{ts['fta']:.1f}</td><td style="{border_css}">{t_ftpct:.1f}</td>
            <td style="{border_css}">{ts['dr']:.1f}</td><td style="{border_css}">{ts['or']:.1f}</td><td style="{border_css}">{ts['tot']:.1f}</td>
            <td style="{border_css}">{ts['as']:.1f}</td><td style="{border_css}">{ts['to']:.1f}</td><td style="{border_css}">{ts['st']:.1f}</td><td style="{border_css}">{ts['pf']:.1f}</td>
        </tr>
    </table>
</div>
"""

def generate_custom_sections_html(offense_df, defense_df, about_df):
    html = "<div style='margin-top: 20px; page-break-inside: avoid;'>"
    def make_section(title, df):
        if df.empty: return ""
        section_html = f"<h3 style='border-bottom: 2px solid #333; margin-bottom:5px; font-size:16px;'>{title}</h3>"
        section_html += "<table style='width:100%; border-collapse:collapse; font-family:Arial; font-size:11px; margin-bottom:15px;'>"
        for _, r in df.iterrows():
            c1 = r.get(df.columns[0], "")
            c2 = r.get(df.columns[1], "")
            section_html += f"<tr><td style='width:30%; border:1px solid #ccc; padding:4px; font-weight:bold; vertical-align:top;'>{c1}</td><td style='border:1px solid #ccc; padding:4px; vertical-align:top;'>{c2}</td></tr>"
        section_html += "</table>"
        return section_html

    html += make_section("Key Facts Offense", offense_df)
    html += make_section("Key Facts Defense", defense_df)
    html += make_section("ALL ABOUT US", about_df)
    html += "</div>"
    return html

# --- ANSICHT: BEARBEITUNG ---
if not st.session_state.print_mode:
    st.title(f"🏀 DBBL Scouting Pro {VERSION}")
    
    st.subheader("1. Spieldaten")
    col_staffel, col_home, col_guest = st.columns([1, 2, 2])
    with col_staffel:
        staffel = st.radio("Staffel:", ["Süd", "Nord"], horizontal=True)
        teams_filtered = {k: v for k, v in TEAMS_DB.items() if v['staffel'] == staffel}
        team_options = {v['name']: k for k, v in teams_filtered.items()}
    with col_home:
        home_name = st.selectbox("Heim-Team:", list(team_options.keys()), index=0, key="sel_home")
        home_id = team_options[home_name]
        st.image(get_logo_url(home_id), width=100)
    with col_guest:
        guest_name = st.selectbox("Gast-Team:", list(team_options.keys()), index=1, key="sel_guest")
        guest_id = team_options[guest_name]
        st.image(get_logo_url(guest_id), width=100)

    st.write("---")
    scout_target = st.radio("Wen möchtest du scouten?", ["Gastteam (Gegner)", "Heimteam"], horizontal=True, key="sel_target")
    target_team_id = guest_id if scout_target == "Gastteam (Gegner)" else home_id

    col_date, col_time = st.columns(2)
    with col_date: date_input = st.date_input("Datum", datetime.date.today(), key="sel_date")
    with col_time: time_input = st.time_input("Tip-Off", datetime.time(16, 0), key="sel_time")

    st.divider()
    if st.button(f"2. Kader von {scout_target} laden", type="primary"):
        api_url = f"https://api-s.dbbl.scb.world/teams/{target_team_id}/{SEASON_ID}/player-stats"
        api_team = f"https://api-s.dbbl.scb.world/seasons/{SEASON_ID}/team-statistics?displayType=MAIN_ROUND&teamId={target_team_id}"
        
        try:
            resp = requests.get(api_url, headers=API_HEADERS)
            resp.raise_for_status()
            data = resp.json()
            raw = data if isinstance(data, list) else data.get('data', [])
            
            resp_t = requests.get(api_team, headers=API_HEADERS)
            team_data_list = resp_t.json()
            ts = {}
            if team_data_list and isinstance(team_data_list, list):
                td = team_data_list[0]
                ts = {
                    'ppg': td.get('pointsPerGame', 0),
                    '2m': td.get('twoPointShotsMadePerGame', 0), '2a': td.get('twoPointShotsAttemptedPerGame', 0), '2pct': td.get('twoPointShotsSuccessPercent', 0),
                    '3m': td.get('threePointShotsMadePerGame', 0), '3a': td.get('threePointShotsAttemptedPerGame', 0), '3pct': td.get('threePointShotsSuccessPercent', 0),
                    'ftm': td.get('freeThrowsMadePerGame', 0), 'fta': td.get('freeThrowsAttemptedPerGame', 0), 'ftpct': td.get('freeThrowsSuccessPercent', 0),
                    'dr': td.get('defensiveReboundsPerGame', 0), 'or': td.get('offensiveReboundsPerGame', 0), 'tot': td.get('totalReboundsPerGame', 0),
                    'as': td.get('assistsPerGame', 0), 'to': td.get('turnoversPerGame', 0), 'st': td.get('stealsPerGame', 0), 'pf': td.get('foulsCommittedPerGame', 0),
                }
            st.session_state.team_stats = ts

            if raw:
                df = pd.json_normalize(raw)
                df.columns = [str(c).lower() for c in df.columns]
                col_map = {
                    'firstname': ['person.firstname', 'firstname'],
                    'lastname': ['person.lastname', 'lastname'],
                    'shirtnumber': ['jerseynumber', 'shirtnumber', 'no'],
                    'id': ['id', 'person.id', 'personid'],
                    'gp': ['matches', 'gamesplayed', 'games', 'gp'],
                    'ppg': ['pointspergame'], 'tot': ['totalreboundspergame'],
                    'min_sec': ['secondsplayedpergame', 'minutespergame', 'avgminutes', 'minutes'],
                    'sec_total': ['secondsplayed', 'totalminutes', 'totalseconds'],
                    '2m': ['twopointshotsmadepergame'], '2a': ['twopointshotsattemptedpergame'], '2pct': ['twopointshotsuccesspercent'],
                    '3m': ['threepointshotsmadepergame'], '3a': ['threepointshotsattemptedpergame'], '3pct': ['threepointshotsuccesspercent'],
                    'ftm': ['freethrowsmadepergame'], 'fta': ['freethrowsattemptedpergame'], 'ftpct': ['freethrowssuccesspercent'],
                    'dr': ['defensivereboundspergame'], 'or': ['offensivereboundspergame'],
                    'as': ['assistspergame'], 'to': ['turnoverspergame'], 'st': ['stealspergame'], 'pf': ['foulscommittedpergame'],
                    'bs': ['blockspergame', 'blockedshotspergame'], # Neu
                    'fgpct': ['fieldgoalsuccesspercent', 'fieldgoalpercentage']
                }
                final_cols = {}
                for t, p_list in col_map.items():
                    for p in p_list:
                        m = [c for c in df.columns if p in c]
                        if m: final_cols[t] = sorted(m, key=len)[0]; break
                
                fn = df[final_cols['firstname']].fillna('') if 'firstname' in final_cols else ''
                ln = df[final_cols['lastname']].fillna('') if 'lastname' in final_cols else ''
                df['NAME_FULL'] = (fn + " " + ln).str.strip()
                df['NR'] = df[final_cols['shirtnumber']].fillna('-').astype(str).str.replace('.0', '', regex=False) if 'shirtnumber' in final_cols else '-'
                df['PLAYER_ID'] = df[final_cols['id']].astype(str) if 'id' in final_cols else ""
                
                def get_v(k): return pd.to_numeric(df[final_cols[k]], errors='coerce').fillna(0) if k in final_cols else pd.Series([0.0]*len(df))
                def pct(v): return round(v*100, 1) if v<=1 else round(v,1)

                df['GP'] = get_v('gp').replace(0, 1)
                min_raw = get_v('min_sec')
                sec_total = get_v('sec_total')
                df['MIN_FINAL'] = min_raw
                mask_zero = df['MIN_FINAL'] <= 0
                df.loc[mask_zero, 'MIN_FINAL'] = sec_total[mask_zero] / df.loc[mask_zero, 'GP']
                df['MIN_DISPLAY'] = df['MIN_FINAL'].apply(format_minutes)
                df['PPG'] = get_v('ppg'); df['TOT'] = get_v('tot')
                df['2M'] = get_v('2m'); df['2A'] = get_v('2a'); df['2PCT'] = get_v('2pct').apply(pct)
                df['3M'] = get_v('3m'); df['3A'] = get_v('3a'); df['3PCT'] = get_v('3pct').apply(pct)
                df['FTM'] = get_v('ftm'); df['FTA'] = get_v('fta'); df['FTPCT'] = get_v('ftpct').apply(pct)
                raw_fg = get_v('fgpct')
                if raw_fg.sum() == 0: df['FG%'] = df['2PCT'] 
                else: df['FG%'] = raw_fg.apply(pct)
                df['DR'] = get_v('dr'); df['OR'] = get_v('or')
                df['AS'] = get_v('as'); df['TO'] = get_v('to'); df['ST'] = get_v('st'); df['PF'] = get_v('pf'); df['BS'] = get_v('bs')
                df['select'] = False
                st.session_state.roster_df = df
                st.session_state.game_meta = {'home_name': home_name, 'home_logo': get_logo_url(home_id), 'guest_name': guest_name, 'guest_logo': get_logo_url(guest_id), 'date': date_input.strftime('%d.%m.%Y'), 'time': time_input.strftime('%H:%M')}
        except Exception as e: st.error(f"Fehler: {e}")

    if st.session_state.roster_df is not None:
        st.subheader("3. Spieler auswählen")
        edited = st.data_editor(st.session_state.roster_df[['select', 'NR', 'NAME_FULL', 'PPG', 'TOT']], column_config={"select": st.column_config.CheckboxColumn("Scout?", default=False)}, disabled=["NR", "NAME_FULL", "PPG", "TOT"], hide_index=True)
        selected_indices = edited[edited['select']].index
        
        if len(selected_indices) > 0:
            st.divider()
            st.subheader("4. Notizen & Key Facts")
            
            with st.form("scouting_form"):
                st.write("**Spieler-Notizen:**")
                selection = st.session_state.roster_df.loc[selected_indices]
                form_results = [] 
                
                for _, row in selection.iterrows():
                    pid = row['PLAYER_ID']
                    c_h, c_c = st.columns([3, 1])
                    c_h.markdown(f"##### #{row['NR']} {row['NAME_FULL']}")
                    saved_c = st.session_state.saved_colors.get(pid, "Grau")
                    try: idx = ["Grau", "Grün", "Rot"].index(saved_c)
                    except: idx = 0
                    col_opt = c_c.selectbox("Markierung", ["Grau", "Grün", "Rot"], key=f"col_{pid}", index=idx, label_visibility="collapsed")
                    
                    c1, c2 = st.columns(2)
                    l1v = st.session_state.saved_notes.get(f"l1_{pid}", ""); l2v = st.session_state.saved_notes.get(f"l2_{pid}", "")
                    l3v = st.session_state.saved_notes.get(f"l3_{pid}", ""); l4v = st.session_state.saved_notes.get(f"l4_{pid}", "")
                    r1v = st.session_state.saved_notes.get(f"r1_{pid}", ""); r2v = st.session_state.saved_notes.get(f"r2_{pid}", "")
                    r3v = st.session_state.saved_notes.get(f"r3_{pid}", ""); r4v = st.session_state.saved_notes.get(f"r4_{pid}", "")

                    l1=c1.text_input("L1", value=l1v, key=f"l1_{pid}", label_visibility="collapsed")
                    l2=c1.text_input("L2", value=l2v, key=f"l2_{pid}", label_visibility="collapsed")
                    l3=c1.text_input("L3", value=l3v, key=f"l3_{pid}", label_visibility="collapsed")
                    l4=c1.text_input("L4", value=l4v, key=f"l4_{pid}", label_visibility="collapsed")
                    r1=c2.text_input("R1", value=r1v, key=f"r1_{pid}", label_visibility="collapsed")
                    r2=c2.text_input("R2", value=r2v, key=f"r2_{pid}", label_visibility="collapsed")
                    r3=c2.text_input("R3", value=r3v, key=f"r3_{pid}", label_visibility="collapsed")
                    r4=c2.text_input("R4", value=r4v, key=f"r4_{pid}", label_visibility="collapsed")
                    st.divider()
                    form_results.append({'row': row, 'pid': pid, 'color': col_opt, 'notes': {'l1': l1, 'l2': l2, 'l3': l3, 'l4': l4, 'r1': r1, 'r2': r2, 'r3': r3, 'r4': r4}})

                st.markdown("### Key Facts")
                c_k1, c_k2, c_k3 = st.columns(3)
                with c_k1: st.caption("Offense"); edited_off = st.data_editor(st.session_state.facts_offense, num_rows="dynamic", key="editor_offense", hide_index=True)
                with c_k2: st.caption("Defense"); edited_def = st.data_editor(st.session_state.facts_defense, num_rows="dynamic", key="editor_defense", hide_index=True)
                with c_k3: st.caption("All About Us"); edited_abt = st.data_editor(st.session_state.facts_about, num_rows="dynamic", key="editor_about", hide_index=True)
                
                st.markdown("### Grafiken")
                uploaded_files = st.file_uploader("Upload", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])

                submitted = st.form_submit_button("Speichern & PDF Generieren", type="primary")

            if submitted:
                st.session_state.facts_offense = edited_off
                st.session_state.facts_defense = edited_def
                st.session_state.facts_about = edited_abt
                
                for item in form_results:
                    pid = item['pid']
                    st.session_state.saved_colors[pid] = item['color']
                    for k, v in item['notes'].items(): st.session_state.saved_notes[f"{k}_{pid}"] = v

                color_map = {"Grau": "#666666", "Grün": "#5c9c30", "Rot": "#d9534f"}
                full_df = st.session_state.roster_df
                html = generate_header_html(st.session_state.game_meta)
                html += generate_top3_html(full_df)
                
                for item in form_results:
                    meta = get_player_metadata(item['pid'])
                    c_hex = color_map[item['color']]
                    html += generate_card_html(item['row'].to_dict(), meta, item['notes'], c_hex)
                
                html += generate_team_stats_html(st.session_state.team_stats)
                
                if uploaded_files:
                    html += "<div style='page-break-before: always;'><h2>Plays & Grafiken</h2>"
                    for up in uploaded_files:
                        b64 = base64.b64encode(up.getvalue()).decode()
                        html += f"<div style='margin-bottom:20px;'><img src='data:image/png;base64,{b64}' style='max_width:100%; border:1px solid #ccc;'></div>"
                    html += "</div>"
                
                html += generate_custom_sections_html(st.session_state.facts_offense, st.session_state.facts_defense, st.session_state.facts_about)
                st.session_state.final_html = html
                st.session_state.print_mode = True
                st.rerun()

else:
    if st.button("⬅️ Zurück (Daten bleiben erhalten)"):
        st.session_state.print_mode = False
        st.rerun()
    st.markdown(st.session_state.final_html, unsafe_allow_html=True)
    st.markdown("""
    <style>
    @media print {
        @page { size: A4; margin: 5mm; }
        body { margin: 0; padding: 0; zoom: 0.65; }
        .block-container { padding: 0 !important; max-width: none !important; width: 100% !important; overflow: visible !important; }
        [data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stToolbar"], footer, .stButton { display: none !important; }
        
        /* Force Tables to Expand */
        table { width: 100% !important; table-layout: fixed !important; }
        
        /* Hide Scrollbars */
        ::-webkit-scrollbar { display: none; }
        
        /* Make all containers overflow visible */
        .stApp, [data-testid="stVerticalBlock"], div { overflow: visible !important; height: auto !important; }
        
        /* Ensure Images Scale */
        img { max-width: 100% !important; height: auto !important; }
    }
    </style>
    """, unsafe_allow_html=True)

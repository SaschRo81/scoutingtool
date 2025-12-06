import streamlit as st
import pandas as pd
import requests
import base64
import datetime
from io import BytesIO
from PIL import Image

# --- KONFIGURATION ---
st.set_page_config(page_title="DBBL Scouting Pro by Sascha Rosanke", layout="wide", page_icon="🏀")

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
    
    # SÜD (Aktualisiert)
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
        if v > 48:
            mins = int(v // 60)
            secs = int(v % 60)
        else:
            mins = int(v)
            secs = int((v % 1) * 60)
        return f"{mins:02d}:{secs:02d}"
    except:
        return "00:00"

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
    except:
        pass
    return "https://via.placeholder.com/150?text=Err"

def get_player_metadata(player_id):
    try:
        url = f"https://api-s.dbbl.scb.world/season-players/{player_id}"
        resp = requests.get(url, headers=API_HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            raw_img = data.get('imageUrl', '')
            opt_img = optimize_image_base64(raw_img) if raw_img else ""
            return {
                'img': opt_img,
                'height': data.get('height', 0),
                'pos': data.get('position', '-')
            }
    except:
        pass
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
    scorers = df.sort_values(by='PPG', ascending=False).head(3)
    rebounders = df.sort_values(by='TOT', ascending=False).head(3)
    shooters = df[df['3M'] >= 0.5].sort_values(by='3PCT', ascending=False).head(3)
    if shooters.empty:
        shooters = df.sort_values(by='3PCT', ascending=False).head(3)
    fts = df[df['FTA'] >= 1.0].sort_values(by='FTPCT', ascending=True).head(3)
    if fts.empty:
        fts = df.sort_values(by='FTPCT', ascending=True).head(3)

    table_style = "width:100%; font-size:11px; border-collapse:collapse; margin-top:5px;"
    th_style = "text-align:center; border-bottom:1px solid #999; font-weight:bold; color:#555;"
    td_name = "text-align:left; border-bottom:1px solid #eee; padding:3px 0;"
    td_val = "text-align:center; border-bottom:1px solid #eee;"

    def build_table(d, headers, keys, bolds):
        h = f"<table style='{table_style}'><tr>"
        for head in headers:
            h += f"<th style='{th_style}'>{head}</th>"
        h += "</tr>"
        for _, r in d.iterrows():
            h += "<tr>"
            for i, k in enumerate(keys):
                style = td_val
                if i == 0:
                    style = td_name
                if i in bolds:
                    style += " font-weight:bold;"
                val = r[k]
                if isinstance(val, float):
                    val = f"{val:.1f}"
                if k == 'NR':
                    val = f"#{val}"
                if k == 'NAME_FULL' and i == 0:
                    val = f"#{r['NR']} {r['NAME_FULL']}"
                if k != 'NR' and k != 'NAME_FULL':
                    h += f"<td style='{style}'>{val}</td>"
                elif k == 'NAME_FULL':
                    h += f"<td style='{style}'>{val}</td>"
            h += "</tr>"
        h += "</table>"
        return h

    h_scorers = build_table(scorers, ["Name", "PPG", "FG%"], ["NAME_FULL", "PPG", "FG%"], [1])
    h_rebs = build_table(rebounders, ["Name", "DR", "OR", "TOT"], ["NAME_FULL", "DR", "OR", "TOT"], [3])
    h_3pt = build_table(shooters, ["Name", "M", "A", "%"], ["NAME_FULL", "3M", "3A", "3PCT"], [3])
    h_ft = build_table(fts, ["Name", "M", "A", "%"], ["NAME_FULL", "FTM", "FTA", "FTPCT"], [3])

    return f"""
<div style="display: flex; flex-direction: row; gap: 15px; margin-bottom: 30px; page-break-inside: avoid; font-family: Arial, sans-serif;">
<div style="flex: 1; border: 1px solid #ccc; padding: 5px;"><div style="font-weight:bold; color:#e35b00; border-bottom: 2px solid #e35b00; font-size:13px;">🔥 Top Scorer</div>{h_scorers}</div>
<div style="flex: 1; border: 1px solid #ccc; padding: 5px;"><div style="font-weight:bold; color:#0055ff; border-bottom: 2px solid #0055ff; font-size:13px;">🗑️ Rebounder</div>{h_rebs}</div>
<div style="flex: 1; border: 1px solid #ccc; padding: 5px;"><div style="font-weight:bold; color:#28a745; border-bottom: 2px solid #28a745; font-size:13px;">🎯 Best 3pt</div>{h_3pt}</div>
<div style="flex: 1; border: 1px solid #ccc; padding: 5px;"><div style="font-weight:bold; color:#dc3545; border-bottom: 2px solid #dc3545; font-size:13px;">⚠️ Worst FT</div>{h_ft}</div>
</div>
"""

def generate_card_html(row, metadata, notes, color_code):
    img_url = metadata['img'] if metadata['img'] else "https://via.placeholder.com/150?text=No+Img"
    try:
        h = float(metadata['height'])
        if h > 3:
            h = h / 100
        height_str = f"{h:.2f}".replace('.', ',')
    except:
        height_str = "-"
    pos_str = clean_pos(metadata['pos'])
    header_style = (
        f"background-color: {color_code}; color: white; padding: 5px 10px; "
        f"font-weight: bold; font-size: 18px; display: flex; justify-content: space-between; "
        f"align-items: center; -webkit-print-color-adjust: exact; print-color-adjust: exact;"
    )
    
    return f"""
<div style="font-family: Arial, sans-serif; border: 1px solid #ccc; margin-bottom: 20px; background-color: white; page-break-inside: avoid;">
<div style="{header_style}"><span>#{row['NR']} {row['NAME_FULL']}</span><span>{height_str} m | Pos: {pos_str}</span></div>
<div style="display: flex; flex-direction: row;">
<div style="width: 120px; min-width: 120px; border-right: 1px solid #ccc;">
    <img src="{img_url}" style="width: 100%; height: 150px; object-fit: cover;" onerror="this.src='https://via.placeholder.com/120x150?text=No+Img'">
</div>
<table style="width: 100%; border-collapse: collapse; font-size: 12px; text-align: center; color: black;">
<tr style="background-color: #f0f0f0; -webkit-print-color-adjust: exact;">
<th rowspan="2" style="border: 1px solid black; padding: 4px;">Min</th><th rowspan="2" style="border: 1px solid black; padding: 4px;">PPG</th>
<th colspan="3" style="border: 1px solid black; padding: 4px;">2P FG</th><th colspan="3" style="border: 1px solid black; padding: 4px;">3P FG</th><th colspan="3" style="border: 1px solid black; padding: 4px;">FT</th>
<th colspan="3" style="border: 1px solid black; padding: 4px;">REB</th>
<th rowspan="2" style="border: 1px solid black; padding: 4px;">AS</th><th rowspan="2" style="border: 1px solid black; padding: 4px;">TO</th><th rowspan="2" style="border: 1px solid black; padding: 4px;">ST</th><th rowspan="2" style="border: 1px solid black; padding: 4px;">PF</th>
</tr>
<tr style="background-color: #f0f0f0; -webkit-print-color-adjust: exact;">
<th style="border: 1px solid black;">M</th><th style="border: 1px solid black;">A</th><th style="border: 1px solid black;">%</th>
<th style="border: 1px solid black;">M</th><th style="border: 1px solid black;">A</th><th style="border: 1px solid black;">%</th>
<th style="border: 1px solid black;">M</th><th style="border: 1px solid black;">A</th><th style="border: 1px solid black;">%</th>
<th style="border: 1px solid black;">DR</th><th style="border: 1px solid black;">O</th><th style="border: 1px solid black;">TOT</th>
</tr>
<tr>
<td style="border: 1px solid black;">{row['MIN_DISPLAY']}</td><td style="border: 1px solid black;">{row['PPG']}</td>
<td style="border: 1px solid black;">{row['2M']}</td><td style="border: 1px solid black;">{row['2A']}</td><td style="border: 1px solid black;">{row['2PCT']}</td>
<td style="border: 1px solid black;">{row['3M']}</td><td style="border: 1px solid black;">{row['3A']}</td><td style="border: 1px solid black;">{row['3PCT']}</td>
<td style="border: 1px solid black;">{row['FTM']}</td><td style="border: 1px solid black;">{row['FTA']}</td><td style="border: 1px solid black;">{row['FTPCT']}</td>
<td style="border: 1px solid black;">{row['DR']}</td><td style="border: 1px solid black;">{row['OR']}</td><td style="border: 1px solid black;">{row['TOT']}</td>
<td style="border: 1px solid black;">{row['AS']}</td><td style="border: 1px solid black;">{row['TO']}</td><td style="border: 1px solid black;">{row['ST']}</td><td style="border: 1px solid black;">{row['PF']}</td>
</tr>
<tr><td colspan="6" style="border: 1px solid black; height: 25px; text-align: left; padding-left: 5px;">{notes['l1']}</td><td colspan="10" style="border: 1px solid black; color: red; font-weight: bold; text-align: left; padding-left: 5px; -webkit-print-color-adjust: exact;">{notes['r1']}</td></tr>
<tr><td colspan="6" style="border: 1px solid black; height: 25px; text-align: left; padding-left: 5px;">{notes['l2']}</td><td colspan="10" style="border: 1px solid black; color: red; font-weight: bold; text-align: left; padding-left: 5px; -webkit-print-color-adjust: exact;">{notes['r2']}</td></tr>
<tr><td colspan="6" style="border: 1px solid black; height: 25px; text-align: left; padding-left: 5px;">{notes['l3']}</td><td colspan="10" style="border: 1px solid black; color: red; font-weight: bold; text-align: left; padding-left: 5px; -webkit-print-color-adjust: exact;">{notes['r3']}</td></tr>
<tr><td colspan="6" style="border: 1px solid black; height: 25px; text-align: left; padding-left: 5px;">{notes['l4']}</td><td colspan="10" style="border: 1px solid black; color: red; font-weight: bold; text-align: left; padding-left: 5px; -webkit-print-color-adjust: exact;">{notes['r4']}</td></tr>
</table>
</div>
</div>
"""

def generate_team_stats_html(team_stats):
    if not team_stats:
        return ""
    ts = team_stats

    def calc_pct(made, att, api_val):
        if api_val > 0:
            return api_val
        if att > 0:
            return (made / att) * 100
        return 0.0

    t_2pct = calc_pct(ts['2m'], ts['2a'], ts['2pct'])
    t_3pct = calc_pct(ts['3m'], ts['3a'], t

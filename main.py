import streamlit as st
import pandas as pd
import requests
import base64
import datetime

# --- KONFIGURATION ---
st.set_page_config(page_title="DBBL Scouting Pro", layout="wide", page_icon="🏀")

API_HEADERS = {
    "accept": "application/json",
    "X-API-Key": "48673298c840c12a1646b737c83e5e5e"
}

# TEAM DATENBANK
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
    131: {"name": "MTV Stuttgart", "staffel": "Süd"},
    158: {"name": "VIMODROM Baskets Jena", "staffel": "Süd"},
    160: {"name": "BBU '01", "staffel": "Süd"},
    159: {"name": "Bamberg Baskets", "staffel": "Süd"}
}

# --- SESSION STATE ---
if 'print_mode' not in st.session_state: st.session_state.print_mode = False
if 'final_html' not in st.session_state: st.session_state.final_html = ""
if 'roster_df' not in st.session_state: st.session_state.roster_df = None
if 'game_meta' not in st.session_state: st.session_state.game_meta = {}

# --- HILFSFUNKTIONEN ---

def get_logo_url(team_id):
    return f"https://api-s.dbbl.scb.world/images/teams/logo/2025/{team_id}"

def format_minutes(val):
    try:
        v = float(val)
        if v == 0: return "00:00"
        if v > 48: mins = int(v // 60); secs = int(v % 60)
        else: mins = int(v); secs = int((v % 1) * 60)
        return f"{mins:02d}:{secs:02d}"
    except: return "00:00"

def clean_pos(pos):
    if not pos or pd.isna(pos): return "-"
    return str(pos).replace('_', ' ').title()

def get_player_metadata(player_id):
    try:
        url = f"https://api-s.dbbl.scb.world/season-players/{player_id}"
        resp = requests.get(url, headers=API_HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            return {'img': data.get('imageUrl', ''), 'height': data.get('height', 0), 'pos': data.get('position', '-')}
    except: pass
    return {'img': '', 'height': 0, 'pos': '-'}

def generate_header_html(meta):
    # WICHTIG: Keine Einrückung im HTML String!
    return f"""
<div style="border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 30px; text-align: center; font-family: Arial, sans-serif; page-break-inside: avoid;">
    <div style="font-size: 14px; color: #666; margin-bottom: 10px;">Scouting Report | {meta['date']} - {meta['time']} Uhr</div>
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
"""

def generate_top3_html(df):
    scorers = df.sort_values(by='PPG', ascending=False).head(3)
    rebounders = df.sort_values(by='TOT', ascending=False).head(3)
    shooters = df[df['3M'] >= 0.5].sort_values(by='3PCT', ascending=False).head(3)
    if shooters.empty: shooters = df.sort_values(by='3PCT', ascending=False).head(3)
    fts = df[df['FTA'] >= 1.0].sort_values(by='FTPCT', ascending=True).head(3)
    if fts.empty: fts = df.sort_values(by='FTPCT', ascending=True).head(3)

    def row_html(d, stat_col, show_pct=False):
        rows = ""
        for _, r in d.iterrows():
            stat_val = r[stat_col]
            val_display = f"{stat_val:.1f}%" if show_pct else f"{stat_val:.1f}"
            rows += f"<tr><td style='border-bottom:1px solid #ddd;'>#{r['NR']} {r['NAME_FULL']}</td><td style='text-align:right; border-bottom:1px solid #ddd;'><b>{val_display}</b></td></tr>"
        return rows

    # WICHTIG: HTML String ganz linksbündig, damit Markdown es nicht als Code-Block erkennt
    html = f"""
<div style="display: flex; flex-direction: row; gap: 20px; margin-bottom: 30px; page-break-inside: avoid; font-family: Arial, sans-serif;">
    <div style="flex: 1; border: 1px solid #ccc; padding: 10px;">
        <div style="font-weight:bold; color:#e35b00; border-bottom: 2px solid #e35b00; margin-bottom:5px;">🔥 Top Scorer (PPG)</div>
        <table style="width:100%; font-size:12px; border-collapse:collapse;">{row_html(scorers, 'PPG')}</table>
    </div>
    <div style="flex: 1; border: 1px solid #ccc; padding: 10px;">
        <div style="font-weight:bold; color:#0055ff; border-bottom: 2px solid #0055ff; margin-bottom:5px;">🗑️ Rebounder (RPG)</div>
        <table style="width:100%; font-size:12px; border-collapse:collapse;">{row_html(rebounders, 'TOT')}</table>
    </div>
    <div style="flex: 1; border: 1px solid #ccc; padding: 10px;">
        <div style="font-weight:bold; color:#28a745; border-bottom: 2px solid #28a745; margin-bottom:5px;">🎯 Best 3pt (%)</div>
        <table style="width:100%; font-size:12px; border-collapse:collapse;">{row_html(shooters, '3PCT', True)}</table>
    </div>
    <div style="flex: 1; border: 1px solid #ccc; padding: 10px;">
        <div style="font-weight:bold; color:#dc3545; border-bottom: 2px solid #dc3545; margin-bottom:5px;">⚠️ Worst FT (%)</div>
        <table style="width:100%; font-size:12px; border-collapse:collapse;">{row_html(fts, 'FTPCT', True)}</table>
    </div>
</div>
"""
    return html

def generate_card_html(row, metadata, notes):
    img_url = metadata['img'] if metadata['img'] else "https://via.placeholder.com/150?text=No+Img"
    try:
        h = float(metadata['height'])
        if h > 3: h = h / 100
        height_str = f"{h:.2f}".replace('.', ',')
    except: height_str = "-"
    pos_str = clean_pos(metadata['pos'])

    # WICHTIG: Linksbündig!
    html = f"""
<div style="font-family: Arial, sans-serif; border: 1px solid #ccc; margin-bottom: 20px; background-color: white; page-break-inside: avoid;">
    <div style="background-color: #5c9c30; color: white; padding: 5px 10px; font-weight: bold; font-size: 18px; display: flex; justify-content: space-between; align-items: center; -webkit-print-color-adjust: exact; print-color-adjust: exact;">
        <span>#{row['NR']} {row['NAME_FULL']}</span>
        <span>{height_str} m | Pos: {pos_str}</span>
    </div>
    <div style="display: flex; flex-direction: row;">
        <div style="width: 120px; min-width: 120px; border-right: 1px solid #ccc;">
            <img src="{img_url}" style="width: 100%; height: 150px; object-fit: cover;" onerror="this.src='https://via.placeholder.com/120x150?text=No+Img'">
        </div>
        <table style="width: 100%; border-collapse: collapse; font-size: 12px; text-align: center; color: black;">
            <tr style="background-color: #f0f0f0; -webkit-print-color-adjust: exact;">
                <th rowspan="2" style="border: 1px solid black; padding: 4px;">Min</th>
                <th rowspan="2" style="border: 1px solid black; padding: 4px;">PPG</th>
                <th colspan="3" style="border: 1px solid black; padding: 4px;">2P FG</th>
                <th colspan="3" style="border: 1px solid black; padding: 4px;">3P FG</th>
                <th colspan="3" style="border: 1px solid black; padding: 4px;">FT</th>
                <th colspan="3" style="border: 1px solid black; padding: 4px;">REB</th>
                <th rowspan="2" style="border: 1px solid black; padding: 4px;">AS</th>
                <th rowspan="2" style="border: 1px solid black; padding: 4px;">TO</th>
                <th rowspan="2" style="border: 1px solid black; padding: 4px;">ST</th>
                <th rowspan="2" style="border: 1px solid black; padding: 4px;">PF</th>
            </tr>
            <tr style="background-color: #f0f0f0; -webkit-print-color-adjust: exact;">
                <th style="border: 1px solid black;">M</th> <th style="border: 1px solid black;">A</th> <th style="border: 1px solid black;">%</th>
                <th style="border: 1px solid black;">M</th> <th style="border: 1px solid black;">A</th> <th style="border: 1px solid black;">%</th>
                <th style="border: 1px solid black;">M</th> <th style="border: 1px solid black;">A</th> <th style="border: 1px solid black;">%</th>
                <th style="border: 1px solid black;">DR</th> <th style="border: 1px solid black;">O</th> <th style="border: 1px solid black;">TOT</th>
            </tr>
            <tr>
                <td style="border: 1px solid black;">{row['MIN_DISPLAY']}</td>
                <td style="border: 1px solid black;">{row['PPG']}</td>
                <td style="border: 1px solid black;">{row['2M']}</td> <td style="border: 1px solid black;">{row['2A']}</td> <td style="border: 1px solid black;">{row['2%']}</td>
                <td style="border: 1px solid black;">{row['3M']}</td> <td style="border: 1px solid black;">{row['3A']}</td> <td style="border: 1px solid black;">{row['3%']}</td>
                <td style="border: 1px solid black;">{row['FTM']}</td> <td style="border: 1px solid black;">{row['FTA']}</td> <td style="border: 1px solid black;">{row['FT%']}</td>
                <td style="border: 1px solid black;">{row['DR']}</td> <td style="border: 1px solid black;">{row['OR']}</td> <td style="border: 1px solid black;">{row['TOT']}</td>
                <td style="border: 1px solid black;">{row['AS']}</td>
                <td style="border: 1px solid black;">{row['TO']}</td>
                <td style="border: 1px solid black;">{row['ST']}</td>
                <td style="border: 1px solid black;">{row['PF']}</td>
            </tr>
            <tr><td colspan="6" style="border: 1px solid black; height: 25px; text-align: left; padding-left: 5px;">{notes['l1']}</td><td colspan="10" style="border: 1px solid black; color: red; font-weight: bold; text-align: left; padding-left: 5px; -webkit-print-color-adjust: exact;">{notes['r1']}</td></tr>
            <tr><td colspan="6" style="border: 1px solid black; height: 25px; text-align: left; padding-left: 5px;">{notes['l2']}</td><td colspan="10" style="border: 1px solid black; color: red; font-weight: bold; text-align: left; padding-left: 5px; -webkit-print-color-adjust: exact;">{notes['r2']}</td></tr>
            <tr><td colspan="6" style="border: 1px solid black; height: 25px; text-align: left; padding-left: 5px;">{notes['l3']}</td><td colspan="10" style="border: 1px solid black; color: red; font-weight: bold; text-align: left; padding-left: 5px; -webkit-print-color-adjust: exact;">{notes['r3']}</td></tr>
            <tr><td colspan="6" style="border: 1px solid black; height: 25px; text-align: left; padding-left: 5px;">{notes['l4']}</td><td colspan="10" style="border: 1px solid black; color: red; font-weight: bold; text-align: left; padding-left: 5px; -webkit-print-color-adjust: exact;">{notes['r4']}</td></tr>
        </table>
    </div>
</div>
"""
    return html

# --- ANSICHT: BEARBEITUNG ---
if not st.session_state.print_mode:
    st.title("🏀 DBBL Scouting: Einzel-Analyse")
    
    # 1. SPIEL DATEN (Heim/Gast/Zeit)
    st.subheader("1. Spieldaten")
    col_staffel, col_home, col_guest = st.columns([1, 2, 2])
    
    with col_staffel:
        staffel = st.radio("Staffel:", ["Süd", "Nord"], horizontal=True)
        teams_filtered = {k: v for k, v in TEAMS_DB.items() if v['staffel'] == staffel}
        team_options = {v['name']: k for k, v in teams_filtered.items()}

    with col_home:
        home_name = st.selectbox("Heim-Team:", list(team_options.keys()), index=0)
        home_id = team_options[home_name]
        st.image(get_logo_url(home_id), width=100)

    with col_guest:
        guest_name = st.selectbox("Gast-Team:", list(team_options.keys()), index=1)
        guest_id = team_options[guest_name]
        st.image(get_logo_url(guest_id), width=100)

    # FRAGE: WEN SCOUTEN?
    st.write("---")
    scout_target = st.radio("Wen möchtest du scouten (Daten laden)?", ["Gastteam (Gegner)", "Heimteam"], horizontal=True)
    target_team_id = guest_id if scout_target == "Gastteam (Gegner)" else home_id

    col_date, col_time = st.columns(2)
    with col_date: date_input = st.date_input("Datum", datetime.date.today())
    with col_time: time_input = st.time_input("Tip-Off", datetime.time(16, 0))

    # DATEN LADEN
    st.divider()
    if st.button(f"2. Kader von {scout_target} laden", type="primary"):
        api_url = f"https://api-s.dbbl.scb.world/teams/{target_team_id}/2025/player-stats"
        try:
            resp = requests.get(api_url, headers=API_HEADERS)
            data = resp.json()
            raw = data if isinstance(data, list) else data.get('data', [])
            if raw:
                df = pd.json_normalize(raw)
                df.columns = [str(c).lower() for c in df.columns]
                
                # Mapping
                col_map = {
                    'firstname': ['person.firstname', 'firstname'],
                    'lastname': ['person.lastname', 'lastname'],
                    'shirtnumber': ['jerseynumber', 'shirtnumber', 'no'],
                    'id': ['id', 'person.id', 'personid'],
                    'ppg': ['pointspergame'], 'tot': ['totalreboundspergame'],
                    '3m': ['threepointshotsmadepergame'], '3pct': ['threepointshotsuccesspercent'], '3a': ['threepointshotsattemptedpergame'],
                    'ftpct': ['freethrowssuccesspercent'], 'fta': ['freethrowsattemptedpergame'],
                    'min_sec': ['secondsplayedpergame', 'minutespergame', 'avgminutes']
                }
                final_cols = {}
                for t, p_list in col_map.items():
                    for p in p_list:
                        m = [c for c in df.columns if p in c]
                        if m:
                            final_cols[t] = sorted(m, key=len)[0]
                            break
                
                fn = df[final_cols['firstname']].fillna('') if 'firstname' in final_cols else ''
                ln = df[final_cols['lastname']].fillna('') if 'lastname' in final_cols else ''
                df['NAME_FULL'] = (fn + " " + ln).str.strip()
                df['NR'] = df[final_cols['shirtnumber']].fillna('-').astype(str).str.replace('.0', '', regex=False) if 'shirtnumber' in final_cols else '-'
                df['PLAYER_ID'] = df[final_cols['id']].astype(str) if 'id' in final_cols else ""
                
                def get_v(k): return pd.to_numeric(df[final_cols[k]], errors='coerce').fillna(0) if k in final_cols else 0.0
                df['PPG'] = get_v('ppg'); df['TOT'] = get_v('tot'); 
                df['3M'] = get_v('3m'); df['3PCT'] = get_v('3pct'); df['3A'] = get_v('3a')
                df['FTPCT'] = get_v('ftpct'); df['FTA'] = get_v('fta')
                
                # Keine Vorauswahl
                df['select'] = False
                
                st.session_state.roster_df = df
                
                # Meta Daten (Formatierung des Datums hier!)
                st.session_state.game_meta = {
                    'home_name': home_name, 'home_logo': get_logo_url(home_id),
                    'guest_name': guest_name, 'guest_logo': get_logo_url(guest_id),
                    'date': date_input.strftime('%d.%m.%Y'), # Hier wird das Datum formatiert
                    'time': time_input.strftime('%H:%M')
                }

        except: st.error("Fehler beim Laden der Daten.")

    # AUSWAHL & INPUT
    if st.session_state.roster_df is not None:
        st.subheader("3. Spieler auswählen")
        edited = st.data_editor(st.session_state.roster_df[['select', 'NR', 'NAME_FULL', 'PPG', 'TOT', 'PLAYER_ID']],
                                column_config={"select": st.column_config.CheckboxColumn("Scout?", default=False), "PLAYER_ID": None},
                                disabled=["NR", "NAME_FULL", "PPG", "TOT"], hide_index=True)
        selected_ids = edited[edited['select']]['PLAYER_ID'].tolist()

        if selected_ids:
            st.divider()
            st.subheader("4. Scouting Bericht & Notizen")
            
            with st.form("input_form"):
                st.write("Notizen eingeben:")
                full_df = st.session_state.roster_df
                selection = full_df[full_df['PLAYER_ID'].isin(selected_ids)]
                
                # Mapping Detail
                col_map_det = {
                    'min_sec': ['secondsplayedpergame', 'minutespergame'],
                    '2m': ['twopointshotsmadepergame'], '2a': ['twopointshotsattemptedpergame'], '2pct': ['twopointshotsuccesspercent'],
                    '3m': ['threepointshotsmadepergame'], '3a': ['threepointshotsattemptedpergame'], '3pct': ['threepointshotsuccesspercent'],
                    'ftm': ['freethrowsmadepergame'], 'fta': ['freethrowsattemptedpergame'], 'ftpct': ['freethrowssuccesspercent'],
                    'dr': ['defensivereboundspergame'], 'or': ['offensivereboundspergame'], 'tot': ['totalreboundspergame'],
                    'as': ['assistspergame'], 'to': ['turnoverspergame'], 'st': ['stealspergame'], 'pf': ['foulscommittedpergame']
                }
                cols = full_df.columns
                final_cols_det = {}
                for t, plist in col_map_det.items():
                    for p in plist:
                        m = [c for c in cols if p in c]
                        if m: final_cols_det[t] = sorted(m, key=len)[0]; break
                
                def get_val_row(r, k): return pd.to_numeric(r[final_cols_det[k]], errors='coerce') if k in final_cols_det else 0.0
                
                results_data = []

                for _, row in selection.iterrows():
                    pid = row['PLAYER_ID']
                    st.markdown(f"**#{row['NR']} {row['NAME_FULL']}**")
                    c1, c2 = st.columns(2)
                    l1 = c1.text_input("L1", key=f"l1_{pid}"); r1 = c2.text_input("R1", key=f"r1_{pid}")
                    l2 = c1.text_input("L2", key=f"l2_{pid}"); r2 = c2.text_input("R2", key=f"r2_{pid}")
                    l3 = c1.text_input("L3", key=f"l3_{pid}"); r3 = c2.text_input("R3", key=f"r3_{pid}")
                    l4 = c1.text_input("L4", key=f"l4_{pid}"); r4 = c2.text_input("R4", key=f"r4_{pid}")
                    st.markdown("---")
                    
                    d = row.to_dict()
                    d['MIN_DISPLAY'] = format_minutes(get_val_row(row, 'min_sec'))
                    def pct(v): return round(v*100, 1) if v<=1 else round(v,1)
                    
                    d['2M']=round(get_val_row(row,'2m'),1); d['2A']=round(get_val_row(row,'2a'),1); d['2%']=pct(get_val_row(row,'2pct'))
                    d['3M']=round(get_val_row(row,'3m'),1); d['3A']=round(get_val_row(row,'3a'),1); d['3%']=pct(get_val_row(row,'3pct'))
                    d['FTM']=round(get_val_row(row,'ftm'),1); d['FTA']=round(get_val_row(row,'fta'),1); d['FT%']=pct(get_val_row(row,'ftpct'))
                    d['DR']=round(get_val_row(row,'dr'),1); d['OR']=round(get_val_row(row,'or'),1); d['TOT']=round(get_val_row(row,'tot'),1)
                    d['AS']=round(get_val_row(row,'as'),1); d['TO']=round(get_val_row(row,'to'),1); d['ST']=round(get_val_row(row,'st'),1); d['PF']=round(get_val_row(row,'pf'),1)
                    
                    notes = {'l1':l1,'l2':l2,'l3':l3,'l4':l4,'r1':r1,'r2':r2,'r3':r3,'r4':r4}
                    results_data.append((d, notes))
                
                st.subheader("5. Grafiken anhängen")
                uploaded_files = st.file_uploader("Plays / Bilder hochladen", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])

                submitted = st.form_submit_button("PDF Ansicht erstellen", type="primary")
            
            if submitted:
                # HTML ZUSAMMENBAUEN
                final_html = generate_header_html(st.session_state.game_meta)
                final_html += generate_top3_html(full_df)
                
                for p_data, p_notes in results_data:
                    meta = get_player_metadata(p_data['PLAYER_ID'])
                    final_html += generate_card_html(p_data, meta, p_notes)
                
                if uploaded_files:
                    final_html += "<div style='page-break-before: always;'><h2>Plays & Grafiken</h2>"
                    for up_file in uploaded_files:
                        bytes_data = up_file.getvalue()
                        b64 = base64.b64encode(bytes_data).decode()
                        final_html += f"<div style='margin-bottom:20px;'><img src='data:image/png;base64,{b64}' style='max_width:100%; border:1px solid #ccc;'></div>"
                    final_html += "</div>"
                
                st.session_state.final_html = final_html
                st.session_state.print_mode = True
                st.rerun()

# --- ANSICHT: DRUCK ---
else:
    if st.button("⬅️ Zurück zur Bearbeitung"):
        st.session_state.print_mode = False
        st.rerun()
    
    st.markdown(st.session_state.final_html, unsafe_allow_html=True)
    
    st.markdown("""
        <style>
            @media print {
                [data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stToolbar"], footer, .stButton {
                    display: none !important;
                }
                .block-container {
                    padding: 0 !important;
                    margin: 0 !important;
                    max_width: 100% !important;
                }
            }
        </style>
    """, unsafe_allow_html=True)

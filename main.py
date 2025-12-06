import streamlit as st
import pandas as pd
import requests

# --- KONFIGURATION ---
st.set_page_config(page_title="DBBL Scouting Pro", layout="wide", page_icon="🏀")

API_HEADERS = {
    "accept": "application/json",
    "X-API-Key": "48673298c840c12a1646b737c83e5e5e"
}

# Teams nach Staffeln getrennt für die Auswahl
TEAMS_NORD = {
    112: "BBC Osnabrück", 121: "TG Neuss Tigers", 116: "Eimsbütteler TV",
    114: "AVIDES Hurricanes", 123: "Bochum AstroLadies", 118: "Metropol Ladies",
    111: "WINGS Leverkusen", 120: "Talents BonnRhöndorf", 113: "Bender Baskets Grünberg",
    122: "TSVE Bielefeld", 117: "LionPride Braunschweig", 115: "ChemCats Chemnitz",
    106: "Veilchen Ladies Göttingen", 119: "Oberhausen", 157: "TuS Lichterfelde",
    156: "Hürther BC"
}

TEAMS_SUED = {
    130: "KuSG Leimen", 126: "Dillingen Diamonds", 132: "QOOL Sharks Würzburg",
    128: "Eisvögel USC Freiburg 2", 134: "TSV 1880 Wasserburg", 129: "Falcons Bad Homburg",
    125: "USC BasCats Heidelberg", 131: "MTV Stuttgart", 127: "DJK Don Bosco Bamberg",
    133: "Rhein-Main Baskets", 124: "ASC Theresianum Mainz", 135: "TSV München-Ost",
    158: "VIMODROM Baskets Jena", 160: "BBU '01", 159: "Bamberg Baskets"
}

# --- HILFSFUNKTIONEN ---

def get_player_metadata(player_id):
    """Holt Bild, Größe und Position vom season-players Endpunkt."""
    try:
        url = f"https://api-s.dbbl.scb.world/season-players/{player_id}"
        resp = requests.get(url, headers=API_HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            # Daten extrahieren mit Fallbacks
            return {
                'img': data.get('imageUrl', ''),
                'height': data.get('height', 0),
                'pos': data.get('position', '-')
            }
    except:
        pass
    return {'img': '', 'height': 0, 'pos': '-'}

def generate_card_html(row, metadata, notes):
    """Erstellt das HTML für den PDF-Druck."""
    
    # Bild URL prüfen
    img_url = metadata['img']
    if not img_url: img_url = "https://via.placeholder.com/150?text=No+Img"

    # Größe formatieren
    try:
        h = float(metadata['height'])
        if h > 3: h = h / 100 # cm in m umrechnen
        height_str = f"{h:.2f}".replace('.', ',')
    except:
        height_str = "-"

    pos_str = metadata['pos'] if metadata['pos'] else "-"

    # HTML Template
    html = f"""
<div style="font-family: Arial, sans-serif; border: 1px solid #ccc; margin-bottom: 20px; background-color: white; page-break-inside: avoid;">
    <div style="background-color: #5c9c30; color: white; padding: 5px 10px; font-weight: bold; font-size: 18px; display: flex; justify-content: space-between; align-items: center; -webkit-print-color-adjust: exact; print-color-adjust: exact;">
        <span>#{row['NR']} {row['NAME_FULL']}</span>
        <span>{height_str} m | Pos: {pos_str}</span>
    </div>
    <div style="display: flex; flex-direction: row;">
        <div style="width: 120px; min-width: 120px; border-right: 1px solid #ccc;">
            <img src="{img_url}" style="width: 100%; height: 150px; object-fit: cover;" 
                 onerror="this.src='https://via.placeholder.com/120x150?text=No+Img'">
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

# --- HAUPTPROGRAMM ---
st.title("🏀 DBBL Scouting: Einzel-Analyse")

# 1. TEAM WAHL
c_team1, c_team2 = st.columns(2)
with c_team1:
    staffel = st.radio("Staffel wählen:", ["Süd", "Nord"], horizontal=True)

if staffel == "Süd":
    teams_dict = TEAMS_SUED
else:
    teams_dict = TEAMS_NORD

with c_team2:
    selected_team_name = st.selectbox("Team wählen:", options=list(teams_dict.values()))
    selected_team_id = [k for k, v in teams_dict.items() if v == selected_team_name][0]

# Session State initialisieren für Datenhaltung
if 'roster_df' not in st.session_state:
    st.session_state.roster_df = None

# Button: Kader Laden
if st.button("1. Kader & Stats laden"):
    api_url = f"https://api-s.dbbl.scb.world/teams/{selected_team_id}/2025/player-stats"
    with st.spinner("Lade Daten..."):
        try:
            resp = requests.get(api_url, headers=API_HEADERS)
            resp.raise_for_status()
            data = resp.json()
            raw_data = data if isinstance(data, list) else data.get('data', [])
            
            if raw_data:
                df = pd.json_normalize(raw_data)
                df.columns = [str(c).lower() for c in df.columns]
                
                # BASIS-DATEN AUFBEREITEN
                col_map = {
                    'firstname': ['person.firstname', 'firstname'],
                    'lastname': ['person.lastname', 'lastname'],
                    'shirtnumber': ['jerseynumber', 'shirtnumber', 'no'],
                    'id': ['id', 'person.id', 'personid'], # WICHTIG FÜR METADATEN API
                    'ppg': ['pointspergame'],
                    'tot_pg': ['totalreboundspergame'],
                    '3m': ['threepointshotsmadepergame'],
                    '3a': ['threepointshotsattemptedpergame'],
                    '3pct': ['threepointshotsuccesspercent'],
                    'ftpct': ['freethrowssuccesspercent'],
                    'fta': ['freethrowsattemptedpergame']
                }
                
                final_cols = {}
                for target, possibilities in col_map.items():
                    for p in possibilities:
                        matches = [c for c in df.columns if p in c]
                        if matches:
                            final_cols[target] = sorted(matches, key=len)[0]
                            break
                
                # Name & Nummer
                fn = df[final_cols['firstname']].fillna('') if 'firstname' in final_cols else ''
                ln = df[final_cols['lastname']].fillna('') if 'lastname' in final_cols else ''
                df['NAME_FULL'] = (fn + " " + ln).str.strip()
                
                if 'shirtnumber' in final_cols:
                    df['NR'] = df[final_cols['shirtnumber']].fillna('-').astype(str).str.replace('.0', '', regex=False)
                else: df['NR'] = '-'

                if 'id' in final_cols: df['PLAYER_ID'] = df[final_cols['id']].astype(str)
                else: df['PLAYER_ID'] = ""

                # Stats für Vorauswahl (Top Scorer etc.)
                def get_val(key): return pd.to_numeric(df[final_cols[key]], errors='coerce').fillna(0) if key in final_cols else 0.0
                df['PPG'] = get_val('ppg')
                df['TOT'] = get_val('tot_pg')
                df['3M'] = get_val('3m')
                df['3PCT'] = get_val('3pct')
                df['FTPCT'] = get_val('ftpct')
                df['FTA'] = get_val('fta')

                # Vorauswahl (Top Scorer, Rebounder, 3er)
                top_scorer = df.sort_values(by='PPG', ascending=False).head(3)
                best_reb = df.sort_values(by='TOT', ascending=False).head(3)
                
                mask_3p = df['3M'] >= 0.5
                best_3pt = df[mask_3p].sort_values(by='3PCT', ascending=False).head(3)
                if best_3pt.empty: best_3pt = df.sort_values(by='3PCT', ascending=False).head(3)
                
                # Wir setzen standardmäßig Häkchen bei den Key Playern
                key_ids = pd.concat([top_scorer, best_reb, best_3pt])['PLAYER_ID'].unique().tolist()
                df['select'] = df['PLAYER_ID'].apply(lambda x: True if x in key_ids else False)

                # Speichern
                st.session_state.roster_df = df
                st.session_state.raw_data_backup = df # Für die volle Stat-Berechnung später
            else:
                st.error("Keine Spieler gefunden.")
        except Exception as e:
            st.error(f"Fehler: {e}")

# 2. AUSWAHL ANZEIGEN (Wenn geladen)
if st.session_state.roster_df is not None:
    st.divider()
    st.subheader("2. Spieler auswählen")
    st.info("Setze Haken bei den Spielern, für die du eine Einzelkarte erstellen willst.")
    
    # Data Editor erlaubt das Ankreuzen
    edited_df = st.data_editor(
        st.session_state.roster_df[['select', 'NR', 'NAME_FULL', 'PPG', 'TOT', 'PLAYER_ID']],
        column_config={
            "select": st.column_config.CheckboxColumn("Scouten?", default=True),
            "PLAYER_ID": None # ID verstecken
        },
        disabled=["NR", "NAME_FULL", "PPG", "TOT"],
        hide_index=True,
        use_container_width=True
    )
    
    # IDs der ausgewählten Spieler holen
    selected_ids = edited_df[edited_df['select']]['PLAYER_ID'].tolist()
    
    # Button: Analyse Starten
    st.divider()
    if st.button("3. Einzelanalyse generieren"):
        st.session_state.selected_ids = selected_ids
        st.rerun()

# 3. ANALYSE & INPUT FORMULAR
if 'selected_ids' in st.session_state and st.session_state.roster_df is not None:
    st.subheader("3. Scouting Bericht & Notizen")
    
    # Wir filtern das Original-DF nach den ausgewählten IDs
    # Aber wir brauchen wieder die Vollen Spalten für die Tabelle (2P, 3P, etc)
    # Da wir oben nur eine Light-Version hatten, nehmen wir das backup oder berechnen neu.
    # Einfacher: Wir nutzen das `roster_df` (das alle Spalten hat, auch die versteckten) 
    # und mappen jetzt nochmal sauber alles für die HTML Ausgabe.
    
    full_df = st.session_state.roster_df
    final_selection = full_df[full_df['PLAYER_ID'].isin(st.session_state.selected_ids)].copy()
    
    # Mapping wiederholen/erweitern für alle Stats (falls oben nicht alle mapped waren)
    # Um sicher zu gehen, nutzen wir die Rohdaten Logik für die Anzeige
    col_map_full = {
        'min_sec_pg': ['secondsplayedpergame'],
        '2pm_pg': ['twopointshotsmadepergame'], '2pa_pg': ['twopointshotsattemptedpergame'], '2pct': ['twopointshotsuccesspercent'],
        '3pm_pg': ['threepointshotsmadepergame'], '3pa_pg': ['threepointshotsattemptedpergame'], '3pct': ['threepointshotsuccesspercent'],
        'ftm_pg': ['freethrowsmadepergame'], 'fta_pg': ['freethrowsattemptedpergame'], 'ftpct': ['freethrowssuccesspercent'],
        'dr_pg': ['defensivereboundspergame'], 'or_pg': ['offensivereboundspergame'], 'tot_pg': ['totalreboundspergame'],
        'as_pg': ['assistspergame'], 'to_pg': ['turnoverspergame'], 'st_pg': ['stealspergame'], 'pf_pg': ['foulscommittedpergame']
    }
    
    cols = full_df.columns
    final_cols_full = {}
    for target, possibilities in col_map_full.items():
        for p in possibilities:
            matches = [c for c in cols if p in c]
            if matches:
                final_cols_full[target] = sorted(matches, key=len)[0]
                break
    
    def get_val(row, key, decimals=1):
        if key in final_cols_full: return pd.to_numeric(row[final_cols_full[key]], errors='coerce') #.fillna(0) -> NaN lassen für Formatierung? Nein, 0 ist ok
        return 0.0
    
    # WICHTIG: Das Formular
    # Alle Inputs kommen hier rein. Erst beim Klick auf "Update" wird neu geladen.
    with st.form("scouting_input_form"):
        st.write("Schreibe deine Notizen in die Felder. Klicke unten auf **'Ansicht aktualisieren'**, um die PDFs zu generieren.")
        
        # Container für Ergebnisse sammeln
        results = []

        for index, row in final_selection.iterrows():
            p_id = str(row['NR']) + "_" + str(row['PLAYER_ID'])
            
            st.markdown(f"#### #{row['NR']} {row['NAME_FULL']}")
            
            # Inputs
            c1, c2 = st.columns(2)
            with c1:
                st.caption("Notizen (Schwarz)")
                l1 = st.text_input("Zeile 1 L", key=f"l1_{p_id}")
                l2 = st.text_input("Zeile 2 L", key=f"l2_{p_id}")
                l3 = st.text_input("Zeile 3 L", key=f"l3_{p_id}")
                l4 = st.text_input("Zeile 4 L", key=f"l4_{p_id}")
            with c2:
                st.caption("Defense/Calls (Rot)")
                r1 = st.text_input("Zeile 1 R", key=f"r1_{p_id}")
                r2 = st.text_input("Zeile 2 R", key=f"r2_{p_id}")
                r3 = st.text_input("Zeile 3 R", key=f"r3_{p_id}")
                r4 = st.text_input("Zeile 4 R", key=f"r4_{p_id}")
            
            st.divider()
            
            # Daten sammeln für HTML Generierung (passiert erst nach Submit)
            player_data = row.to_dict()
            
            # Stats aufbereiten für HTML
            player_data['MIN_DISPLAY'] = "00:00"
            if 'min_sec_pg' in final_cols_full:
                 t = get_val(row, 'min_sec_pg'); 
                 player_data['MIN_DISPLAY'] = f"{int(t//60):02d}:{int(t%60):02d}" if t > 48 else f"{int(t)}:{int((t%1)*60):02d}"

            def fix_pct(val): return round(val * 100, 1) if val <= 1.0 and val > 0 else round(val, 1)

            player_data['2M'] = round(get_val(row, '2pm_pg'), 1); player_data['2A'] = round(get_val(row, '2pa_pg'), 1); player_data['2%'] = fix_pct(get_val(row, '2pct'))
            player_data['3M'] = round(get_val(row, '3pm_pg'), 1); player_data['3A'] = round(get_val(row, '3pa_pg'), 1); player_data['3%'] = fix_pct(get_val(row, '3pct'))
            player_data['FTM'] = round(get_val(row, 'ftm_pg'), 1); player_data['FTA'] = round(get_val(row, 'fta_pg'), 1); player_data['FT%'] = fix_pct(get_val(row, 'ftpct'))
            player_data['DR'] = round(get_val(row, 'dr_pg'), 1); player_data['OR'] = round(get_val(row, 'or_pg'), 1); player_data['TOT'] = round(get_val(row, 'tot_pg'), 1)
            player_data['AS'] = round(get_val(row, 'as_pg'), 1); player_data['TO'] = round(get_val(row, 'to_pg'), 1); 
            player_data['ST'] = round(get_val(row, 'st_pg'), 1); player_data['PF'] = round(get_val(row, 'pf_pg'), 1)
            
            notes = {'l1':l1, 'l2':l2, 'l3':l3, 'l4':l4, 'r1':r1, 'r2':r2, 'r3':r3, 'r4':r4}
            
            results.append((player_data, notes))

        # SUBMIT BUTTON
        update_btn = st.form_submit_button("Ansicht aktualisieren (PDF erstellen)", type="primary")

    # WENN SUBMIT GEDRÜCKT -> HTML GENERIEREN
    if update_btn:
        st.success("Ansicht aktualisiert! Scrolle nach unten für die Druckansicht.")
        st.markdown("---")
        st.subheader("🖨️ Druckansicht (Strg + P)")
        
        for p_data, p_notes in results:
            # 1. Metadaten Live holen (Bild, Größe)
            # Wir machen das hier, damit wir nicht 100 Calls am Anfang machen, sondern nur für die Auswahl
            meta = get_player_metadata(p_data['PLAYER_ID'])
            
            # 2. HTML Generieren
            html_code = generate_card_html(p_data, meta, p_notes)
            st.markdown(html_code, unsafe_allow_html=True)

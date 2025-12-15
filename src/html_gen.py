# --- START OF FILE src/html_gen.py ---
import pandas as pd

def generate_header_html(meta):
    return f"""
    <div style='text-align:center; padding-bottom:10px; border-bottom:2px solid #333; margin-bottom:20px;'>
        <div style='display:flex; justify-content:space-between; align-items:center;'>
            <div style='width:20%; text-align:left;'><img src='{meta.get('home_logo', '')}' style='max-height:80px; max-width:100%;'></div>
            <div style='width:60%; text-align:center;'>
                <h1 style='margin:0; font-size:24px;'>Scouting Report: {meta.get('selected_target', 'Gegner')}</h1>
                <h2 style='margin:5px 0; font-size:18px;'>{meta.get('home_name')} vs {meta.get('guest_name')}</h2>
                <p style='margin:0; font-size:14px; color:#555;'>Datum: {meta.get('date')} | Zeit: {meta.get('time')} Uhr</p>
            </div>
            <div style='width:20%; text-align:right;'><img src='{meta.get('guest_logo', '')}' style='max-height:80px; max-width:100%;'></div>
        </div>
    </div>
    """

def generate_top3_html(df: pd.DataFrame) -> str:
    if df is None or df.empty: return ""
    
    # Sicherstellen, dass Spalten existieren (Fallback)
    for col in ["PPG", "TOT", "3M", "3PCT", "FTA", "FTPCT", "DR", "OR"]:
        if col not in df.columns: df[col] = 0

    scorers = df.sort_values(by="PPG", ascending=False).head(3)
    rebounders = df.sort_values(by="TOT", ascending=False).head(3)
    
    # Shooter: Mind. 0.5 Treffer pro Spiel, sortiert nach Quote
    shooters = df[df["3M"] >= 0.5].sort_values(by="3PCT", ascending=False).head(3)
    if shooters.empty: shooters = df.sort_values(by="3PCT", ascending=False).head(3)
    
    fts = df[df["FTA"] >= 1.0].sort_values(by="FTPCT", ascending=True).head(3) # Schlechteste Werfer zuerst? Oder beste? Hier ascending=True -> Schlechteste (Hack-a-Shaq) oder Beste? 
    # Üblicherweise Top 3 -> Beste. Also ascending=False
    fts = df.sort_values(by="FTPCT", ascending=False).head(3)

    def build_box(d, keys, cols, bolds=[], color="#333", title=""):
        h = f"<div style='flex:1; border:1px solid #ccc; margin:0 5px; font-size:12px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);'>"
        h += f"<div style='background:{color}; color:white; padding:4px; font-weight:bold; text-align:center;'>{title}</div>"
        h += "<table style='width:100%; border-collapse:collapse;'>"
        h += "<tr style='background:#f0f0f0; font-size:10px;'>" + "".join([f"<th style='padding:4px; text-align:center;'>{k}</th>" for k in keys]) + "</tr>"
        for _, r in d.iterrows():
            h += "<tr>"
            for i, k in enumerate(cols):
                val = r[k]
                style = f"padding:4px; border-bottom:1px solid #eee; text-align:center;"
                if i in bolds: style += " font-weight:bold;"
                
                # Name abkürzen
                if k == "NAME_FULL": 
                    parts = str(val).split(" ")
                    val = parts[-1] if parts else val # Nur Nachname
                    style += " text-align:left;"
                
                # Zahlen formatieren
                if isinstance(val, float):
                    if k in ["3PCT", "FTPCT", "2PCT", "FG%"]: val = f"{int(val)}%"
                    else: val = round(val, 1)
                
                h += f"<td style='{style}'>{val}</td>"
            h += "</tr>"
        h += "</table></div>"
        return h

    html = "<h3 style='margin-top:0; border-bottom:1px solid #ccc; padding-bottom:5px;'>Key Stats Leader</h3>"
    html += "<div style='display:flex; justify-content:space-between; margin-bottom:20px;'>"
    html += build_box(scorers, ["#", "Name", "PPG", "FG%"], ["NR", "NAME_FULL", "PPG", "FG%"], [2], "#e35b00", "Top Scorer")
    html += build_box(rebounders, ["#", "Name", "D", "O", "TOT"], ["NR", "NAME_FULL", "DR", "OR", "TOT"], [4], "#0055ff", "Rebounding")
    html += build_box(shooters, ["#", "Name", "3M", "3A", "%"], ["NR", "NAME_FULL", "3M", "3A", "3PCT"], [4], "#28a745", "3-Point Shooters")
    html += "</div>"
    return html

def generate_card_html(row, meta, notes, color_code):
    """
    Erzeugt die HTML-Karte für einen Spieler.
    FIX: Bildgröße begrenzt, damit es nicht verzerrt.
    """
    # Name formatieren
    full_name = row.get("NAME_FULL", "Unknown")
    
    # Image Handling
    img_src = meta.get('img')
    if not img_src:
        # Fallback Placeholder (Graues Männchen)
        img_src = "https://via.placeholder.com/150x200/cccccc/ffffff?text=No+Img"

    # Tabellen-Styling für Stats
    def td(v, b=False): 
        s = "padding:3px 5px; border:1px solid #ccc; text-align:center; font-size:12px;"
        if b: s+= " font-weight:bold; background-color:#f9f9f9;"
        return f"<td style='{s}'>{v}</td>"

    # Notizen Felder
    def note_row(label, val_l, val_r):
        return f"""
        <tr>
            <td style='border:1px solid #ddd; padding:4px; font-size:11px; color:#666; width:15%; vertical-align:top;'>{label}</td>
            <td style='border:1px solid #ddd; padding:4px; font-size:12px; width:42%; vertical-align:top; background:#fff;'>{val_l}</td>
            <td style='border:1px solid #ddd; padding:4px; font-size:12px; width:43%; vertical-align:top; background:#fff;'>{val_r}</td>
        </tr>
        """

    html = f"""
    <div style='border:1px solid #999; margin-bottom:15px; page-break-inside:avoid; background-color:#fff; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);'>
        <!-- Header Leiste mit Farbe -->
        <div style='background-color:{color_code}; color:white; padding:5px 10px; font-weight:bold; font-size:14px; border-bottom:1px solid #666;'>
            #{row['NR']} {full_name} <span style='float:right; font-weight:normal; font-size:12px;'>{row.get('POS', '')} | {meta.get('height','-')} | {meta.get('age','-')} J</span>
        </div>
        
        <table style='width:100%; border-collapse:collapse;'>
            <tr>
                <!-- LINKE SPALTE: BILD -->
                <!-- WICHTIG: width festlegen und vertical-align top, damit das Bild nicht mittig schwimmt -->
                <td style='width:130px; vertical-align:top; padding:0; border-right:1px solid #ccc; background-color:#f0f0f0;'>
                    <div style='width:130px; height:180px; overflow:hidden; display:flex; justify-content:center; align-items:start;'>
                        <!-- Bild CSS: width:100% füllt die 130px. height:auto erhält Aspect Ratio. min-height sorgt dafür, dass es nicht zu klein ist. -->
                        <img src='{img_src}' style='width:100%; height:auto; object-fit:cover; object-position:top;'>
                    </div>
                    <div style='padding:5px; text-align:center; font-size:11px; color:#333; border-top:1px solid #ccc;'>
                        <b>GP:</b> {int(row.get('GP',0))}<br>
                        <b>MIN:</b> {row.get('MIN_DISPLAY','-')}
                    </div>
                </td>

                <!-- RECHTE SPALTE: STATS & NOTIZEN -->
                <td style='vertical-align:top; padding:0;'>
                    <!-- STATS TABELLE -->
                    <table style='width:100%; border-collapse:collapse; margin-bottom:5px;'>
                        <tr style='background-color:#eee; font-size:11px;'>
                            <th style='border:1px solid #ccc; padding:3px;'>PPG</th>
                            <th style='border:1px solid #ccc; padding:3px;' colspan='3'>2P FG</th>
                            <th style='border:1px solid #ccc; padding:3px;' colspan='3'>3P FG</th>
                            <th style='border:1px solid #ccc; padding:3px;' colspan='3'>Free Throws</th>
                            <th style='border:1px solid #ccc; padding:3px;'>REB</th>
                            <th style='border:1px solid #ccc; padding:3px;'>AST</th>
                            <th style='border:1px solid #ccc; padding:3px;'>TO</th>
                        </tr>
                        <tr style='font-size:10px; color:#555;'>
                            <td style='border:1px solid #ccc;'></td>
                            <td style='border:1px solid #ccc; text-align:center;'>M</td><td style='border:1px solid #ccc; text-align:center;'>A</td><td style='border:1px solid #ccc; text-align:center;'>%</td>
                            <td style='border:1px solid #ccc; text-align:center;'>M</td><td style='border:1px solid #ccc; text-align:center;'>A</td><td style='border:1px solid #ccc; text-align:center;'>%</td>
                            <td style='border:1px solid #ccc; text-align:center;'>M</td><td style='border:1px solid #ccc; text-align:center;'>A</td><td style='border:1px solid #ccc; text-align:center;'>%</td>
                            <td style='border:1px solid #ccc;'></td><td style='border:1px solid #ccc;'></td><td style='border:1px solid #ccc;'></td>
                        </tr>
                        <tr>
                            {td(row['PPG'], True)}
                            {td(row['2M'])} {td(row['2A'])} {td(row['2PCT'])}
                            {td(row['3M'])} {td(row['3A'])} {td(row['3PCT'])}
                            {td(row['FTM'])} {td(row['FTA'])} {td(row['FTPCT'])}
                            {td(row['TOT'], True)} {td(row['AS'])} {td(row['TO'])}
                        </tr>
                    </table>

                    <!-- NOTIZEN TABELLE -->
                    <table style='width:100%; border-collapse:collapse; margin-top:0;'>
                        {note_row("Off / Def", notes.get(f"l1_{row['PLAYER_ID']}",""), notes.get(f"r1_{row['PLAYER_ID']}",""))}
                        {note_row("Stärken", notes.get(f"l2_{row['PLAYER_ID']}",""), notes.get(f"r2_{row['PLAYER_ID']}",""))}
                        {note_row("Schwächen", notes.get(f"l3_{row['PLAYER_ID']}",""), notes.get(f"r3_{row['PLAYER_ID']}",""))}
                        {note_row("Sonstiges", notes.get(f"l4_{row['PLAYER_ID']}",""), notes.get(f"r4_{row['PLAYER_ID']}",""))}
                    </table>
                </td>
            </tr>
        </table>
    </div>
    """
    return html

def generate_team_stats_html(ts):
    if not ts: return ""
    
    def r(v): return round(v, 1) if isinstance(v, float) else v
    
    html = """
    <div style='page-break-before:always; margin-top:20px;'>
        <h2 style='border-bottom:2px solid #333; padding-bottom:5px;'>Team Statistiken (Saison Durchschnitt)</h2>
        <table style='width:100%; border-collapse:collapse; font-size:14px;'>
            <tr style='background-color:#333; color:white;'>
                <th style='padding:8px; text-align:left;'>Kategorie</th>
                <th style='padding:8px; text-align:center;'>Wert</th>
                <th style='padding:8px; text-align:left; border-left:1px solid #555;'>Kategorie</th>
                <th style='padding:8px; text-align:center;'>Wert</th>
            </tr>
    """
    
    data = [
        ("Punkte", ts.get("ppg"), "Rebounds Total", ts.get("tot")),
        ("FG %", ts.get("2pct"), "Defensive Reb", ts.get("dr")),
        ("3er %", ts.get("3pct"), "Offensive Reb", ts.get("or")),
        ("Freiwurf %", ts.get("ftpct"), "Assists", ts.get("as")),
        ("Turnovers", ts.get("to"), "Steals", ts.get("st")),
        ("Fouls", ts.get("pf"), "Blocks", ts.get("bs"))
    ]
    
    for i, (l1, v1, l2, v2) in enumerate(data):
        bg = "#f9f9f9" if i % 2 == 0 else "#fff"
        html += f"""
        <tr style='background-color:{bg}; border-bottom:1px solid #ddd;'>
            <td style='padding:8px;'><b>{l1}</b></td>
            <td style='padding:8px; text-align:center;'>{r(v1)}</td>
            <td style='padding:8px; border-left:1px solid #ddd;'><b>{l2}</b></td>
            <td style='padding:8px; text-align:center;'>{r(v2)}</td>
        </tr>
        """
        
    html += "</table></div>"
    return html

def generate_custom_sections_html(df_off, df_def, df_about):
    html = "<div style='margin-top:30px;'>"
    
    def render_section(title, df, color):
        if df is None or df.empty: return ""
        # Prüfen ob Inhalte da sind (manchmal ist df nicht empty, hat aber leere rows)
        has_content = False
        for c in df.columns:
            if df[c].astype(str).str.strip().str.len().sum() > 0: has_content = True
        
        if not has_content: return ""

        h = f"<h3 style='border-bottom:2px solid {color}; color:{color}; margin-top:20px;'>{title}</h3>"
        h += "<ul style='list-style-type:none; padding:0;'>"
        for _, row in df.iterrows():
            fokus = str(row.get('Fokus', '')).strip()
            desc = str(row.get('Beschreibung', '')).strip()
            if fokus or desc:
                h += f"<li style='margin-bottom:8px; padding:8px; background:#f4f4f4; border-left:4px solid {color};'>"
                if fokus: h += f"<strong>{fokus}:</strong> "
                h += f"{desc}</li>"
        h += "</ul>"
        return h

    html += render_section("Offense Keys", df_off, "#e35b00")
    html += render_section("Defense Keys", df_def, "#0055ff")
    html += render_section("General / About", df_about, "#333333")
    html += "</div>"
    return html
# --- END OF FILE src/html_gen.py ---

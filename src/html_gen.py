import pandas as pd
from src.utils import clean_pos

def generate_header_html(meta):
    return f"""
<div class="report-header">
    <div style="text-align: right; font-size: 12px; color: #888; margin-bottom: 5px;">DBBL Scouting Pro by Sascha Rosanke</div>
    <h1 class="report-title">Scouting Report | {meta['date']} - {meta['time']} Uhr</h1>
    <div class="matchup-container">
        <div class="team-logo-box">
            <img src="{meta['home_logo']}" class="team-logo-img">
            <div class="team-name-text">{meta['home_name']}</div>
        </div>
        <div class="vs-text">VS</div>
        <div class="team-logo-box">
            <img src="{meta['guest_logo']}" class="team-logo-img">
            <div class="team-name-text">{meta['guest_name']}</div>
        </div>
    </div>
</div>
"""

def generate_top3_html(df: pd.DataFrame) -> str:
    scorers = df.sort_values(by="PPG", ascending=False).head(3)
    rebounders = df.sort_values(by="TOT", ascending=False).head(3)
    shooters = df[df["3M"] >= 0.5].sort_values(by="3PCT", ascending=False).head(3)
    if shooters.empty: shooters = df.sort_values(by="3PCT", ascending=False).head(3)
    fts = df[df["FTA"] >= 1.0].sort_values(by="FTPCT", ascending=True).head(3)
    if fts.empty: fts = df.sort_values(by="FTPCT", ascending=True).head(3)
    
    assisters = df.sort_values(by="AS", ascending=False).head(3)
    stealers = df.sort_values(by="ST", ascending=False).head(3)
    turnovers = df.sort_values(by="TO", ascending=False).head(3)
    blocks = df.sort_values(by="BS", ascending=False).head(3)
    fouls = df.sort_values(by="PF", ascending=False).head(3)

    FONT_SIZE = "20px"

    def build_box(d, headers, keys, bolds, color, title):
        h = f"<div class='stat-box'>"
        h += f"<div class='stat-title' style='border-top: 4px solid {color}; color: {color}; font-size: 22px; padding: 5px;'>{title}</div>"
        h += f"<table class='top3-table' style='width:100%; font-size: {FONT_SIZE}; border-collapse: collapse;'>"
        h += "<tr>"
        for head in headers: 
            h += f"<th style='padding:4px; background-color:#f2f2f2; border-bottom:1px solid #ccc;'>{head}</th>"
        h += "</tr>"
        for _, r in d.iterrows():
            h += "<tr>"
            for i, k in enumerate(keys):
                val = r[k]
                style = f"padding:4px; border-bottom:1px solid #eee; font-size: {FONT_SIZE};"
                if i in bolds: style += " font-weight:bold;"
                if k == "NAME_FULL": val = val.split(" ")[-1]
                elif isinstance(val, float): val = f"{val:.1f}"
                h += f"<td style='{style}'>{val}</td>"
            h += "</tr>"
        h += "</table></div>"
        return h

    html = "<div class='top3-container'>"
    html += build_box(scorers, ["#", "Name", "PPG", "FG%"], ["NR", "NAME_FULL", "PPG", "FG%"], [2], "#e35b00", "Top Scorer")
    html += build_box(rebounders, ["#", "Name", "D", "O", "TOT"], ["NR", "NAME_FULL", "DR", "OR", "TOT"], [4], "#0055ff", "Rebounds")
    html += build_box(shooters, ["#", "Name", "M", "A", "%"], ["NR", "NAME_FULL", "3M", "3A", "3PCT"], [4], "#28a745", "3-Points")
    html += "</div>"
    
    html += "<div class='top3-container'>"
    html += build_box(fts, ["#", "Name", "M", "A", "%"], ["NR", "NAME_FULL", "FTM", "FTA", "FTPCT"], [4], "#dc3545", "Weak FT")
    html += build_box(assisters, ["#", "Name", "AS"], ["NR", "NAME_FULL", "AS"], [2], "#ffc107", "Assists")
    html += build_box(turnovers, ["#", "Name", "TO"], ["NR", "NAME_FULL", "TO"], [2], "#fd7e14", "Turnovers")
    html += "</div>"
    
    html += "<div class='top3-container'>"
    html += build_box(stealers, ["#", "Name", "ST"], ["NR", "NAME_FULL", "ST"], [2], "#6f42c1", "Steals")
    html += build_box(blocks, ["#", "Name", "BS"], ["NR", "NAME_FULL", "BS"], [2], "#343a40", "Blocks")
    html += build_box(fouls, ["#", "Name", "PF"], ["NR", "NAME_FULL", "PF"], [2], "#20c997", "Fouls")
    html += "</div>"
    return html

def generate_card_html(row, metadata, notes, color_code):
    img_url = metadata["img"] if metadata["img"] else "https://via.placeholder.com/150?text=No+Img"
    try:
        h = float(metadata["height"])
        if h > 3: h = h / 100
        height_str = f"{h:.2f}".replace(".", ",")
    except: height_str = "-"
    pos_str = clean_pos(metadata["pos"])

    return f"""
<div class="player-card">
    <div class="card-header" style="background-color: {color_code};">
        <span>#{row['NR']} {row['NAME_FULL']}</span>
        <span>{height_str} m | Pos: {pos_str}</span>
    </div>
    <div class="card-body">
        <table class="layout-table">
            <tr>
                <td class="layout-img-cell">
                    <img src="{img_url}" class="player-img">
                </td>
                <td class="layout-stats-cell">
                    <table class="stats-table">
                        <tr class="bg-gray">
                            <th rowspan="2">Min</th><th rowspan="2">PPG</th>
                            <th colspan="3">2P FG</th><th colspan="3">3P FG</th><th colspan="3">FT</th>
                            <th colspan="3">REB</th><th rowspan="2">AS</th><th rowspan="2">TO</th><th rowspan="2">ST</th><th rowspan="2">PF</th>
                        </tr>
                        <tr class="bg-gray">
                            <th>M</th><th>A</th><th>%</th><th>M</th><th>A</th><th>%</th><th>M</th><th>A</th><th>%</th>
                            <th>D</th><th>O</th><th>TOT</th>
                        </tr>
                        <tr class="font-bold">
                            <td>{row['MIN_DISPLAY']}</td><td>{row['PPG']}</td>
                            <td>{row['2M']}</td><td>{row['2A']}</td><td>{row['2PCT']}</td>
                            <td>{row['3M']}</td><td>{row['3A']}</td><td>{row['3PCT']}</td>
                            <td>{row['FTM']}</td><td>{row['FTA']}</td><td>{row['FTPCT']}</td>
                            <td>{row['DR']}</td><td>{row['OR']}</td><td>{row['TOT']}</td>
                            <td>{row['AS']}</td><td>{row['TO']}</td><td>{row['ST']}</td><td>{row['PF']}</td>
                        </tr>
                        <tr class="note-row"><td colspan="6" class="note-left">{notes.get('l1','')}</td><td colspan="10" class="note-right">{notes.get('r1','')}</td></tr>
                        <tr class="note-row"><td colspan="6" class="note-left">{notes.get('l2','')}</td><td colspan="10" class="note-right">{notes.get('r2','')}</td></tr>
                        <tr class="note-row"><td colspan="6" class="note-left">{notes.get('l3','')}</td><td colspan="10" class="note-right">{notes.get('r3','')}</td></tr>
                        <tr class="note-row"><td colspan="6" class="note-left">{notes.get('l4','')}</td><td colspan="10" class="note-right">{notes.get('r4','')}</td></tr>
                    </table>
                </td>
            </tr>
        </table>
    </div>
</div>
"""

def generate_team_stats_html(ts):
    if not ts: return ""
    def calc_pct(m, a, api): return api if api > 0 else (m/a*100 if a>0 else 0)
    
    return f"""
<div class="team-stats-container">
    <h2 style="border-bottom: 2px solid #333; padding-bottom: 5px;">Team Stats (AVG)</h2>
    <table class="stats-table" style="font-size: 20px;">
        <tr class="bg-gray font-bold">
            <th rowspan="2" style="padding: 4px;">PPG</th>
            <th colspan="3">2P FG</th><th colspan="3">3P FG</th><th colspan="3">FT</th>
            <th colspan="3">REB</th><th rowspan="2">AS</th><th rowspan="2">TO</th><th rowspan="2">ST</th><th rowspan="2">PF</th>
        </tr>
        <tr class="bg-gray font-bold">
            <th>M</th><th>A</th><th>%</th><th>M</th><th>A</th><th>%</th><th>M</th><th>A</th><th>%</th>
            <th>D</th><th>O</th><th>TOT</th>
        </tr>
        <tr class="font-bold" style="background-color: #f9f9f9;">
            <td style="padding: 8px;">{ts['ppg']:.1f}</td>
            <td>{ts['2m']:.1f}</td><td>{ts['2a']:.1f}</td><td>{calc_pct(ts['2m'],ts['2a'],ts['2pct']):.1f}</td>
            <td>{ts['3m']:.1f}</td><td>{ts['3a']:.1f}</td><td>{calc_pct(ts['3m'],ts['3a'],ts['3pct']):.1f}</td>
            <td>{ts['ftm']:.1f}</td><td>{ts['fta']:.1f}</td><td>{calc_pct(ts['ftm'],ts['fta'],ts['ftpct']):.1f}</td>
            <td>{ts['dr']:.1f}</td><td>{ts['or']:.1f}</td><td>{ts['tot']:.1f}</td>
            <td>{ts['as']:.1f}</td><td>{ts['to']:.1f}</td><td>{ts['st']:.1f}</td><td>{ts['pf']:.1f}</td>
        </tr>
    </table>
</div>
"""

def generate_custom_sections_html(offense_df, defense_df, about_df):
    html = "<div style='page-break-before: always;'>"
    def make_section(title, df):
        if df.empty: return ""
        sh = f"<h3 style='border-bottom: 2px solid #333; margin-bottom:10px; font-size: 26px;'>{title}</h3>"
        sh += "<table style='width:100%; border-collapse:collapse; margin-bottom:20px;'>"
        
        font_size = "22px"

        for _, r in df.iterrows():
            c1 = r.get(df.columns[0], "")
            c2 = r.get(df.columns[1], "")
            sh += "<tr>"
            sh += f"<td style='width:30%; border:1px solid #ccc; padding:8px; font-weight:bold; vertical-align:top; font-size:{font_size};'>{c1}</td>"
            sh += f"<td style='border:1px solid #ccc; padding:8px; vertical-align:top; font-size:{font_size};'>{c2}</td>"
            sh += "</tr>"
        sh += "</table>"
        return sh

    html += make_section("Key Facts Offense", offense_df)
    html += make_section("Key Facts Defense", defense_df)
    html += make_section("ALL ABOUT US", about_df)
    html += "</div>"
    return html

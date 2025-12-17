# --- START OF FILE src/html_gen.py ---

import pandas as pd
import copy
from src.utils import clean_pos

def generate_header_html(meta):
    return f"""
<div class="report-header">
<div style="text-align: right; font-size: 12px; color: #888; margin-bottom: 5px;">DBBL Scouting Pro by Sascha Rosanke</div>
<h1 class="report-title" style="line-height: 1.3;">
Scouting Report | {meta['date']}<br>
<span style="font-size: 0.6em; font-weight: normal;">{meta['time']}</span>
</h1>
<div class="matchup-container" style="display: flex; flex-direction: row; align-items: center; justify-content: center; gap: 50px; margin-top: 20px;">
<div class="team-logo-box" style="text-align: center;">
<img src="{meta['home_logo']}" class="team-logo-img">
<div class="team-name-text">{meta['home_name']}</div>
</div>
<div class="vs-text" style="margin: 0 20px;">VS</div>
<div class="team-logo-box" style="text-align: center;">
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

    FONT_SIZE = "14px"

    def build_box(d, headers, keys, bolds, color, title):
        h = f"<div class='stat-box'>"
        h += f"<div class='stat-title' style='border-top: 4px solid {color}; color: {color}; font-size: 18px; padding: 5px; font-weight:bold;'>{title}</div>"
        h += f"<table class='top3-table'>"
        h += "<tr>"
        for head in headers: 
            h += f"<th>{head}</th>"
        h += "</tr>"
        for _, r in d.iterrows():
            h += "<tr>"
            for i, k in enumerate(keys):
                val = r[k]
                align = "left" if k == "NAME_FULL" else "center"
                if k == "NAME_FULL": val = val.split(" ")[-1]
                elif isinstance(val, float): val = f"{val:.1f}"
                style = f"text-align:{align}; font-size: {FONT_SIZE};"
                if i in bolds: style += " font-weight:bold;"
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

    c_green = "#5c9c30"; c_gray = "#999999"; c_red = "#d9534f"
    legend_html = f"""
<div style="display: flex; gap: 30px; margin-top: 5px; margin-bottom: 20px; font-size: 14px; color: #333;">
<div style="display: flex; align-items: center;"><div style="width: 15px; height: 15px; background-color: {c_green}; margin-right: 8px; border: 1px solid #ccc;"></div><strong>Shooter</strong></div>
<div style="display: flex; align-items: center;"><div style="width: 15px; height: 15px; background-color: {c_gray}; margin-right: 8px; border: 1px solid #ccc;"></div>Normal</div>
<div style="display: flex; align-items: center;"><div style="width: 15px; height: 15px; background-color: {c_red}; margin-right: 8px; border: 1px solid #ccc;"></div>Non-Shooter</div>
</div>"""
    return html + legend_html

def generate_card_html(row, metadata, notes, color_code):
    img_url = metadata["img"] if metadata["img"] else "https://via.placeholder.com/150?text=No+Img"
    try:
        h = float(metadata["height"])
        if h > 3: h = h / 100
        height_str = f"{h:.2f}".replace(".", ",")
    except: height_str = "-"
    pos_str = clean_pos(metadata["pos"])
    
    stats_header = """<tr class="bg-gray"><th rowspan="2">Min</th><th rowspan="2">PPG</th><th colspan="3">2P FG</th><th colspan="3">3P FG</th><th colspan="3">FT</th><th colspan="3">REB</th><th rowspan="2">AS</th><th rowspan="2">TO</th><th rowspan="2">ST</th><th rowspan="2">PF</th></tr><tr class="bg-gray"><th>M</th><th>A</th><th>%</th><th>M</th><th>A</th><th>%</th><th>M</th><th>A</th><th>%</th><th>D</th><th>O</th><th>TOT</th></tr>"""
    stats_row = f'<tr class="font-bold"><td>{row["MIN_DISPLAY"]}</td><td>{row["PPG"]}</td><td>{row["2M"]}</td><td>{row["2A"]}</td><td>{row["2PCT"]}</td><td>{row["3M"]}</td><td>{row["3A"]}</td><td>{row["3PCT"]}</td><td>{row["FTM"]}</td><td>{row["FTA"]}</td><td>{row["FTPCT"]}</td><td>{row["DR"]}</td><td>{row["OR"]}</td><td>{row["TOT"]}</td><td>{row["AS"]}</td><td>{row["TO"]}</td><td>{row["ST"]}</td><td>{row["PF"]}</td></tr>'
    
    note_rows = ""
    for i in range(1, 5):
        l_note = notes.get(f'l{i}', '')
        r_note = notes.get(f'r{i}', '')
        note_rows += f'<tr class="note-row"><td colspan="6">{l_note}</td><td colspan="12" class="note-right" style="color: #d9534f; font-weight: bold;">{r_note}</td></tr>'

    return f"""
<div class="player-card">
<div class="card-header" style="background-color: {color_code};"><span>#{row['NR']} {row['NAME_FULL']}</span><span>{height_str} m | Pos: {pos_str}</span></div>
<div class="card-body">
<table class="layout-table"><tr>
<td class="layout-img-cell"><img src="{img_url}" class="player-img"></td>
<td class="layout-stats-cell">
<table class="stats-table">
{stats_header}
{stats_row}
{note_rows}
</table>
</td>
</tr></table>
</div>
</div>"""

def generate_team_stats_html(ts):
    if not ts: return ""
    def calc_pct(m, a, api): return api if api > 0 else (m/a*100 if a>0 else 0)
    return f"""
<div class="team-stats-container"><h2 style="border-bottom: 2px solid #333; padding-bottom: 5px;">Team Stats (AVG)</h2>
<table class="stats-table" style="font-size: 16px;">
<tr class="bg-gray font-bold"><th rowspan="2" style="padding: 4px;">PPG</th><th colspan="3">2P FG</th><th colspan="3">3P FG</th><th colspan="3">FT</th><th colspan="3">REB</th><th rowspan="2">AS</th><th rowspan="2">TO</th><th rowspan="2">ST</th><th rowspan="2">PF</th></tr>
<tr class="bg-gray font-bold"><th>M</th><th>A</th><th>%</th><th>M</th><th>A</th><th>%</th><th>M</th><th>A</th><th>%</th><th>D</th><th>O</th><th>TOT</th></tr>
<tr class="font-bold" style="background-color: #f9f9f9;"><td style="padding: 8px;">{ts['ppg']:.1f}</td><td>{ts['2m']:.1f}</td><td>{ts['2a']:.1f}</td><td>{calc_pct(ts['2m'],ts['2a'],ts['2pct']):.1f}</td><td>{ts['3m']:.1f}</td><td>{ts['3a']:.1f}</td><td>{calc_pct(ts['3m'],ts['3a'],ts['3pct']):.1f}</td><td>{ts['ftm']:.1f}</td><td>{ts['fta']:.1f}</td><td>{calc_pct(ts['ftm'],ts['fta'],ts['ftpct']):.1f}</td><td>{ts['dr']:.1f}</td><td>{ts['or']:.1f}</td><td>{ts['tot']:.1f}</td><td>{ts['as']:.1f}</td><td>{ts['to']:.1f}</td><td>{ts['st']:.1f}</td><td>{ts['pf']:.1f}</td></tr>
</table>
</div>"""

def generate_custom_sections_html(offense_df, defense_df, about_df):
    html = "<div style='page-break-before: always;'>"
    def make_section(title, df):
        if df.empty: return ""
        sh = f"<h3 style='border-bottom: 2px solid #333; margin-bottom:10px; font-size: 20px;'>{title}</h3>"
        sh += "<table style='width:100%; border-collapse:collapse; margin-bottom:20px;'>"
        for _, r in df.iterrows():
            c1 = r.get(df.columns[0], ""); c2 = r.get(df.columns[1], "")
            sh += f"<tr><td style='width:25%; border:1px solid #ccc; padding:6px; font-weight:bold; vertical-align:top; font-size:14px; background:#f9f9f9;'>{c1}</td><td style='border:1px solid #ccc; padding:6px; vertical-align:top; font-size:14px;'>{c2}</td></tr>"
        return sh + "</table>"
    html += make_section("Key Facts Offense", offense_df)
    html += make_section("Key Facts Defense", defense_df)
    html += make_section("ALL ABOUT US", about_df)
    return html + "</div>"

def generate_comparison_html(h_stats_in, g_stats_in, h_name, g_name):
    if not h_stats_in or not g_stats_in: return "Keine Daten für Vergleich verfügbar."
    import copy
    h_stats = copy.deepcopy(h_stats_in); g_stats = copy.deepcopy(g_stats_in)
    def get_pct(stats, cat):
        if stats.get(f'{cat}pct', 0) > 0: return stats[f'{cat}pct']
        m = stats.get(f'{cat}m', 0); a = stats.get(f'{cat}a', 0)
        return (m / a * 100) if a > 0 else 0.0
    metrics = [("Points Per Game", "ppg", False, False), ("Field Goal %", "FG%", True, False), ("3-Point %", "3pct", True, False), ("Free Throw %", "ftpct", True, False), ("Rebounds (Total)", "tot", False, False), ("Defensive Rebs", "dr", False, False), ("Offensive Rebs", "or", False, False), ("Assists", "as", False, False), ("Turnovers", "to", False, True), ("Steals", "st", False, False), ("Blocks", "bs", False, False), ("Fouls", "pf", False, True)]
    for stats in [h_stats, g_stats]:
        fg_m = stats.get('2m', 0) + stats.get('3m', 0); fg_a = stats.get('2a', 0) + stats.get('3a', 0)
        stats['FG%'] = (fg_m / fg_a * 100) if fg_a > 0 else 0.0
        stats['3pct'] = get_pct(stats, '3'); stats['ftpct'] = get_pct(stats, 'ft')
        if 'bs' not in stats: stats['bs'] = 0.0
    
    html = f"""<div style="margin: 20px 0; font-family: sans-serif;"><h3 style="text-align: center; border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 0;">Head-to-Head (Saison-Schnitt)</h3><table style="width: 100%; border-collapse: collapse; font-size: 16px;"><tr style="background-color: #333; color: white;"><th style="padding: 12px; text-align: right; width: 35%;">{h_name}</th><th style="padding: 12px; text-align: center; width: 30%; background-color: #555;">Statistik</th><th style="padding: 12px; text-align: left; width: 35%;">{g_name}</th></tr>"""
    
    for label, key, is_pct, lower_better in metrics:
        val_h = h_stats.get(key, 0.0); val_g = g_stats.get(key, 0.0)
        fmt_h = f"{val_h:.1f}" + ("%" if is_pct else ""); fmt_g = f"{val_g:.1f}" + ("%" if is_pct else "")
        
        # FIX: Farbe explizit setzen!
        style_h = "padding: 8px; text-align: right; border-bottom: 1px solid #eee; color: #333;"
        style_g = "padding: 8px; text-align: left; border-bottom: 1px solid #eee; color: #333;"
        style_label = "padding: 8px; text-align: center; color: #666; font-size: 14px; border-bottom: 1px solid #eee;"
        
        if val_h != val_g:
            is_h_better = (val_h < val_g) if lower_better else (val_h > val_g)
            if is_h_better: style_h += " font-weight: bold; color: #2e7d32;"
            else: style_g += " font-weight: bold; color: #2e7d32;"
            
        html += f"""<tr><td style="{style_h}">{fmt_h}</td><td style="{style_label}">{label}</td><td style="{style_g}">{fmt_g}</td></tr>"""
    return html + "</table></div>"

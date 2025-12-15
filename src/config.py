import streamlit as st

# Version
VERSION = "v5.0"

# --- API KONFIGURATION ---
try:
    # Wir holen den Key NUR aus den Secrets
    API_KEY = st.secrets["dbbl_api_key"]
except Exception:
    # Wenn der Key fehlt, brechen wir kontrolliert ab
    st.error("🚨 API-Key fehlt! Bitte in den Streamlit Cloud Settings unter 'Secrets' eintragen.")
    st.stop()

API_HEADERS = {
    "accept": "application/json",
    "X-API-Key": API_KEY,
}
SEASON_ID = "2025"

# Teams Datenbank
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
    159: {"name": "Medikamente per Klick Bamberg Baskets", "staffel": "Süd"},
}

# Zentrales CSS
# --- CSS STYLES ---
CSS_STYLES = """
<style>
    @page { margin: 5mm; size: A4 portrait; }
    body { font-family: sans-serif; -webkit-print-color-adjust: exact; }
    
    /* HEADER */
    .report-header { text-align: center; border-bottom: 3px solid #333; margin-bottom: 20px; padding-bottom: 10px; }
    .report-title { margin: 5px 0; font-size: 24px; text-transform: uppercase; }
    .matchup-container { display: flex; justify-content: space-between; align-items: center; margin-top: 15px; padding: 0 20px; }
    .team-logo-box { width: 25%; text-align: center; }
    
    /* Logos festnageln */
    .team-logo-img { height: 80px; width: auto; display: block; margin: 0 auto; }
    
    .team-name-text { font-weight: bold; margin-top: 5px; font-size: 14px; }
    .vs-text { font-size: 28px; font-weight: bold; color: #555; width: 10%; text-align: center; }

    /* TOP 3 BOXES */
    .top3-container { display: flex; gap: 10px; margin-bottom: 15px; }
    .stat-box { flex: 1; border: 1px solid #ccc; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
    .stat-title { background: #f9f9f9; font-weight: bold; text-align: center; text-transform: uppercase; font-size: 14px !important; }
    .top3-table th { background: #eee; font-size: 10px; text-align: center; }
    .top3-table td { text-align: center; padding: 4px; font-size: 11px; }

    /* PLAYER CARD */
    .player-card { border: 1px solid #999; margin-bottom: 15px; page-break-inside: avoid; background-color: #fff; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); }
    .card-header { color: white; padding: 6px 10px; font-weight: bold; font-size: 14px; border-bottom: 1px solid #666; display: flex; justify-content: space-between; }
    
    .layout-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
    
    /* BILD STEUERUNG */
    /* Wir nutzen jetzt background-image im HTML, daher ist die img Klasse weniger wichtig, 
       aber die Zelle muss die Größe erzwingen */
    .layout-img-cell { 
        width: 130px; 
        height: 160px;
        vertical-align: top; 
        padding: 0; 
        background-color: #f0f0f0; 
        border-right: 1px solid #ccc; 
        overflow: hidden; /* WICHTIG: Alles was übersteht abschneiden */
    }
    
    /* STATS TABELLE */
    .layout-stats-cell { vertical-align: top; padding: 0; }
    .stats-table { width: 100%; border-collapse: collapse; font-size: 12px; }
    .stats-table th, .stats-table td { border: 1px solid #ccc; padding: 4px; text-align: center; }
    .bg-gray { background-color: #eee; }
    .font-bold { font-weight: bold; }
    
    /* NOTIZEN */
    .note-row td { text-align: left; vertical-align: top; border: 1px solid #ddd; padding: 4px; height: 18px; }
    .note-left { font-size: 11px; color: #666; background: #fcfcfc; font-weight: bold; }
    .note-right { font-size: 12px; background: #fff; }

    /* TEAM STATS */
    .team-stats-container { margin-top: 20px; page-break-before: always; }
</style>
"""

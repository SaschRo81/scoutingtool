import streamlit as st

# Version
VERSION = "v4.1 (Modular)"

# API Konfiguration
try:
    API_KEY = st.secrets["dbbl_api_key"]
except Exception:
    API_KEY = "" # Fallback oder Fehler werfen

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
CSS_STYLES = """
<style>
    body { font-family: 'Arial', sans-serif; font-size: 12px; }
    
    .report-header { text-align: center; border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 30px; }
    .report-title { font-size: 26px; font-weight: bold; margin: 0; color: #000; }
    .matchup-container { display: flex; align-items: center; justify-content: center; gap: 40px; margin-top: 10px; }
    .team-logo-box { text-align: center; }
    .team-logo-img { height: 60px; max-width: 150px; object-fit: contain; }
    .vs-text { font-size: 24px; font-weight: bold; color: #333; }

    .top3-container { display: flex; flex-direction: row; gap: 10px; margin-bottom: 20px; page-break-inside: avoid; }
    .stat-box { flex: 1; border: 1px solid #ccc; }
    .stat-title { padding: 4px; font-weight: bold; font-size: 13px; border-bottom: 1px solid #eee; }
    .top3-table { width: 100%; font-size: 11px; border-collapse: collapse; }
    .top3-table th { background-color: #f9f9f9; text-align: center; padding: 3px; border-bottom: 1px solid #eee; }
    .top3-table td { text-align: center; padding: 3px; border-bottom: 1px solid #eee; }

    .player-card { 
        border: 1px solid #ccc; margin-bottom: 15px; 
        background-color: white; page-break-inside: avoid; 
        font-family: Arial, sans-serif;
    }
    .card-header { 
        color: white; padding: 3px 10px; font-weight: bold; font-size: 14px; 
        display: flex; justify-content: space-between; align-items: center;
        -webkit-print-color-adjust: exact; print-color-adjust: exact;
    }
    .card-body { display: flex; flex-direction: row; }
    .player-img-box { width: 80px; min-width: 80px; border-right: 1px solid #ccc; }
    .player-img { width: 100%; height: 125px; object-fit: cover; }
    
    .stats-table { width: 100%; border-collapse: collapse; font-size: 11px; text-align: center; color: black; }
    .stats-table th, .stats-table td { border: 1px solid #ccc; padding: 2px 1px; }
    .bg-gray { background-color: #f0f0f0; -webkit-print-color-adjust: exact; }
    .font-bold { font-weight: bold; }
    
    .note-row td { height: 20px; text-align: left; padding-left: 5px; }
    .note-left { font-weight: normal; }
    .note-right { color: red; font-weight: bold; -webkit-print-color-adjust: exact; }

    .team-stats-container { margin-top: 30px; page-break-inside: avoid; }
    
    @media print {
        body { -webkit-print-color-adjust: exact; zoom: 0.7; }
        .no-print { display: none; }
    }
</style>
"""

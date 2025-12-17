import streamlit as st

# Version
VERSION = "v5.1"

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
    116: {"name": "Eimsbütteler TV", "staffel": "Nord"},
    114: {"name": "AVIDES Hurricanes", "staffel": "Nord"},
    123: {"name": "Bochum AstroLadies", "staffel": "Nord"},
    111: {"name": "WINGS Leverkusen", "staffel": "Nord"},
    120: {"name": "Talents BonnRhöndorf", "staffel": "Nord"},
    113: {"name": "Bender Baskets Grünberg", "staffel": "Nord"},
    117: {"name": "LionPride Braunschweig", "staffel": "Nord"},
    115: {"name": "ChemCats Chemnitz", "staffel": "Nord"},
    106: {"name": "Veilchen Ladies Göttingen", "staffel": "Nord"},
    119: {"name": "Oberhausen", "staffel": "Nord"},
    157: {"name": "TuS Lichterfelde", "staffel": "Nord"},
    156: {"name": "Hürther BC", "staffel": "Nord"},
    # SÜD
    124: {"name": "ASC Theresianum Mainz", "staffel": "Süd"},
    126: {"name": "Dillingen Diamonds", "staffel": "Süd"},
    130: {"name": "KuSG Leimen", "staffel": "Süd"},
    132: {"name": "QOOL Sharks Würzburg", "staffel": "Süd"},
    128: {"name": "Eisvögel USC Freiburg 2", "staffel": "Süd"},
    134: {"name": "TSV 1880 Wasserburg", "staffel": "Süd"},
    129: {"name": "Falcons Bad Homburg", "staffel": "Süd"},
    125: {"name": "USC BasCats Heidelberg", "staffel": "Süd"},
    131: {"name": "Lou's Foodtruck MTV Stuttgart", "staffel": "Süd"},
    158: {"name": "VIMODROM Baskets Jena", "staffel": "Süd"},
    160: {"name": "BBU '01", "staffel": "Süd"},
    159: {"name": "Medikamente per Klick Bamberg Baskets", "staffel": "Süd"},
}

# Zentrales CSS - OPTIMIERT FÜR PDF
CSS_STYLES = """
<style>
    body { font-family: 'Arial', sans-serif; font-size: 12px; }
    
    /* --- HEADER BEREICH --- */
    .report-header { text-align: center; border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 30px; }
    .report-title { font-size: 32px; font-weight: bold; margin: 0 0 10px 0; color: #000; }
    .matchup-container { display: flex; align-items: center; justify-content: center; gap: 50px; margin-top: 15px; }
    .team-logo-box { text-align: center; }
    .team-logo-img { height: 90px; max-width: 200px; object-fit: contain; }
    .team-name-text { font-size: 18px; font-weight: bold; margin-top: 8px; }
    .vs-text { font-size: 30px; font-weight: bold; color: #333; }

    /* --- TOP 3 BOXEN --- */
    .top3-container { display: flex; flex-direction: row; gap: 10px; margin-bottom: 20px; page-break-inside: avoid; }
    .stat-box { flex: 1; border: 1px solid #ccc; }
    .top3-table { width: 100%; font-size: 12px; border-collapse: collapse; }
    /* Headers der Top 3 Boxen */
    .top3-table th { background-color: #f2f2f2; text-align: center; padding: 4px; border-bottom: 1px solid #999; font-weight: bold;}
    /* Datenzellen der Top 3 Boxen */
    .top3-table td { padding: 4px; border-bottom: 1px solid #eee; vertical-align: middle; }

    /* --- SPIELER KARTE --- */
    .player-card { 
        border: 1px solid #ccc; margin-bottom: 15px; 
        background-color: white; page-break-inside: avoid; 
        font-family: Arial, sans-serif;
    }
    
    .card-header { 
        color: white; padding: 5px 12px; font-weight: bold; font-size: 16px;   
        display: flex; justify-content: space-between; align-items: center;
        -webkit-print-color-adjust: exact; print-color-adjust: exact; line-height: 1.2;
    }

    .card-body { width: 100%; }
    
    .layout-table { width: 100%; border-collapse: collapse; border: none; margin: 0; padding: 0; table-layout: fixed; }
    
    /* BILDSPALTE: Fix auf 80px Breite */
    .layout-img-cell {
        width: 80px;
        min-width: 80px;
        max-width: 80px;
        vertical-align: top;
        padding: 0;
        border-right: 1px solid #ccc;
        background-color: #fff;
    }
    
    /* Das Bild passt sich der Breite an */
    .player-img { 
        width: 100%; 
        height: auto;
        object-fit: cover; 
        display: block; 
    }
    
    .layout-stats-cell { vertical-align: top; padding: 0; width: auto; }
    
    /* STATS TABELLE */
    .stats-table { width: 100%; border-collapse: collapse; font-size: 13px; text-align: center; color: black; }
    
    .stats-table th, .stats-table td { 
        border: 1px solid #ddd; /* Feinere Linien */
        padding: 4px 2px;       /* Weniger Padding seitlich für Header */
        vertical-align: middle;
    }

    .bg-gray { background-color: #f0f0f0; -webkit-print-color-adjust: exact; }
    .font-bold { font-weight: bold; }
    
    /* --- NOTIZEN DESIGN (Gestrichelte Linien) --- */
    .note-row td { 
        height: 28px;           /* Angenehme Höhe zum Schreiben */
        text-align: left; 
        padding-left: 5px;
        font-size: 16px;
        vertical-align: bottom; /* Text liegt auf der Linie */
        border: none;           /* Keine Box-Rahmen */
        border-bottom: 1px dashed #999; /* Schreiblinie */
        color: #444;            /* Dunkelgrauer Text falls ausgefüllt */
    }
    
    /* Entfernt den Rahmen ganz links und rechts bei Notizen für cleaneren Look */
    .note-row td:first-child { border-left: none; }
    .note-row td:last-child { border-right: none; }

    .note-right { color: red; font-weight: bold; -webkit-print-color-adjust: exact; border-left: 1px solid #ccc !important; }

    .team-stats-container { margin-top: 30px; page-break-inside: avoid; }
    
    @media print {
        body { -webkit-print-color-adjust: exact; zoom: 0.44; }
        .no-print { display: none; }
    }
</style>
"""

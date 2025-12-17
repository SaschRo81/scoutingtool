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
# --- IN src/config.py ---

CSS_STYLES = """
<style>
    body { 
        font-family: 'Arial', sans-serif; 
        font-size: 16px; /* Basis deutlich erhöht */
        line-height: 1.4;
    }
    
    /* --- HEADER --- */
    .report-header { text-align: center; border-bottom: 3px solid #333; padding-bottom: 15px; margin-bottom: 25px; }
    .report-title { font-size: 36px; font-weight: bold; margin: 0; }
    .team-name-text { font-size: 22px; font-weight: bold; }
    .vs-text { font-size: 34px; font-weight: bold; }

    /* --- TOP 3 BOXEN --- */
    .stat-box { flex: 1; border: 2px solid #ccc; }
    .top3-table { width: 100%; font-size: 18px; border-collapse: collapse; }
    .top3-table th { background-color: #f2f2f2; padding: 6px; border-bottom: 2px solid #666; font-size: 16px; }
    .top3-table td { padding: 8px 4px; border-bottom: 1px solid #eee; }

    /* --- SPIELER KARTE --- */
    .player-card { border: 2px solid #999; margin-bottom: 20px; page-break-inside: avoid; }
    
    .card-header { 
        color: white; padding: 10px 15px; font-weight: bold; 
        font-size: 22px; /* Große Namen */
        display: flex; justify-content: space-between; 
        -webkit-print-color-adjust: exact; 
    }

    /* BILDSPALTE: Auf ca. 2,5cm skaliert für 2cm Bildinhalt */
    .layout-img-cell {
        width: 85px; 
        min-width: 85px;
        vertical-align: top;
        border-right: 2px solid #ccc;
    }
    .player-img { width: 100%; height: auto; display: block; }

    /* STATS TABELLE IN DER KARTE */
    .stats-table { width: 100%; border-collapse: collapse; font-size: 18px; text-align: center; }
    .stats-table th { font-size: 14px; padding: 6px 2px; background-color: #f0f0f0; border: 1px solid #ccc; }
    .stats-table td { padding: 10px 2px; border: 1px solid #ccc; font-weight: bold; font-size: 20px; }

    /* NOTIZEN / SCHREIBLINIEN */
    .note-row td { 
        height: 35px; /* Mehr Platz zum Schreiben */
        font-size: 20px;
        border: none !important;
        border-bottom: 2px dashed #666 !important; /* Kräftigere Strichlinie */
        vertical-align: bottom;
        padding-bottom: 5px;
    }
    .note-right { border-left: 2px solid #ccc !important; color: red !important; }

    /* TEAM STATS UNTEN */
    .team-stats-container { margin-top: 30px; }
    .team-stats-container table td { font-size: 22px; padding: 12px; }

    @media print {
        body { zoom: 1.0; } /* Zoom entfernen für sauberen Druck */
    }
</style>
"""

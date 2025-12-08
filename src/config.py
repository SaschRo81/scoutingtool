import streamlit as st

# Version
VERSION = "v4.3 (Secure Mode)"

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
CSS_STYLES = """
<style>
    body { font-family: 'Arial', sans-serif; font-size: 12px; }
    
    /* --- HEADER BEREICH --- */
    .report-header { text-align: center; border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 30px; }
    
    /* Scouting Report Titel größer (H1) */
    .report-title { font-size: 32px; font-weight: bold; margin: 0 0 10px 0; color: #000; }
    
    .matchup-container { display: flex; align-items: center; justify-content: center; gap: 50px; margin-top: 15px; }
    .team-logo-box { text-align: center; }
    
    /* Logos größer */
    .team-logo-img { height: 90px; max-width: 200px; object-fit: contain; }
    
    /* Teamnamen größer */
    .team-name-text { font-size: 18px; font-weight: bold; margin-top: 8px; }
    
    .vs-text { font-size: 30px; font-weight: bold; color: #333; }

    /* --- TOP 3 BOXEN --- */
    .top3-container { display: flex; flex-direction: row; gap: 10px; margin-bottom: 20px; page-break-inside: avoid; }
    .stat-box { flex: 1; border: 1px solid #ccc; }
    .top3-table { width: 100%; font-size: 11px; border-collapse: collapse; }
    .top3-table th { background-color: #f2f2f2; text-align: center; padding: 3px; border-bottom: 1px solid #eee; }
    .top3-table td { text-align: center; padding: 3px; border-bottom: 1px solid #eee; }

    /* --- SPIELER KARTE --- */
    .player-card { 
        border: 1px solid #ccc; margin-bottom: 15px; 
        background-color: white; page-break-inside: avoid; 
        font-family: Arial, sans-serif;
    }
    
    /* Header (Farb-Balken): Text größer & vertikal zentriert */
    .card-header { 
        color: white; 
        padding: 5px 12px; /* Mehr Padding */
        font-weight: bold; 
        font-size: 18px;   /* Größere Schrift */
        display: flex; 
        justify-content: space-between; 
        align-items: center; /* Vertikal zentrieren */
        -webkit-print-color-adjust: exact; print-color-adjust: exact;
        line-height: 1.2;
    }

    .card-body { width: 100%; }
    
    /* Layout Tabelle (Bild links, Stats rechts) */
    .layout-table {
        width: 100%; border-collapse: collapse; border: none; margin: 0; padding: 0; table-layout: fixed;
    }
    .layout-img-cell {
        width: 160px;
        min-width: 160px;
        max-width: 160px;
        vertical-align: top;
        padding: 0;
        border-right: 1px solid #ccc;
    }
    .layout-stats-cell {
        vertical-align: top;
        padding: 0;
        width: auto;
    }
    /* Das Bild selbst */
    .player-img { 
        width: 100%; 
        height: 100%;      /* <--- HIER ERHÖHEN (z.B. auf 160px oder 180px) */
        object-fit: cover; 
        display: block; 
    }
    
    /* Stats Tabelle */
    .stats-table { 
        width: 100%; border-collapse: collapse; 
        font-size: 17px; /* Größe für Zoom 0.44 */
        text-align: center; color: black; white-space: nowrap;
    }
    
    /* HIER GEÄNDERT: Helleres Grau für Tabellenköpfe */
    .bg-gray { 
        background-color: #e6e6e6; /* Deutlich heller als vorher */
        -webkit-print-color-adjust: exact; 
    }
    
    .stats-table th, .stats-table td { 
        border: 1px solid #ccc; 
        padding: 1px 0px; 
        letter-spacing: -0.5px;
    }

    .font-bold { font-weight: bold; }
    .note-row td { height: 20px; text-align: left; padding-left: 5px; }
    .note-left { font-weight: normal; }
    .note-right { color: red; font-weight: bold; -webkit-print-color-adjust: exact; }

    .team-stats-container { margin-top: 30px; page-break-inside: avoid; }
    
    @media print {
        body { -webkit-print-color-adjust: exact; zoom: 0.44; }
        .no-print { display: none; }
    }
</style>
"""

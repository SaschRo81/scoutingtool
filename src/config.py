import streamlit as st

# Version
VERSION = "v5.4"

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

# Zentrales CSS - EXTREM VERGRÖßERT FÜR DRUCK
CSS_STYLES = """
<style>
    /* Basis: Sehr groß, damit es nach dem Rauszoomen im PDF lesbar bleibt */
    body { font-family: 'Arial', sans-serif; font-size: 18px; }
    
    /* --- HEADER BEREICH --- */
    .report-header { text-align: center; border-bottom: 4px solid #333; padding-bottom: 20px; margin-bottom: 30px; }
    .report-title { font-size: 48px; font-weight: bold; margin: 0 0 15px 0; color: #000; }
    
    .matchup-container { display: flex; align-items: center; justify-content: center; gap: 40px; margin-top: 20px; }
    .team-logo-box { text-align: center; }
    .team-logo-img { height: 140px; max-width: 300px; object-fit: contain; } /* Logos riesig */
    .team-name-text { font-size: 28px; font-weight: bold; margin-top: 10px; }
    .vs-text { font-size: 50px; font-weight: bold; color: #333; }

    /* --- TOP 3 BOXEN --- */
    .top3-container { display: flex; flex-direction: row; gap: 15px; margin-bottom: 30px; page-break-inside: avoid; }
    .stat-box { flex: 1; border: 2px solid #999; }
    .top3-table { width: 100%; font-size: 18px; border-collapse: collapse; }
    .top3-table th { background-color: #f2f2f2; text-align: center; padding: 8px; border-bottom: 2px solid #999; font-weight: bold; font-size: 20px;}
    .top3-table td { padding: 8px; border-bottom: 1px solid #ccc; vertical-align: middle; font-weight: bold;}

    /* --- SPIELER KARTE --- */
    .player-card { 
        border: 2px solid #999; margin-bottom: 25px; 
        background-color: white; page-break-inside: avoid; 
        font-family: Arial, sans-serif;
    }
    
    .card-header { 
        color: white; padding: 10px 15px; font-weight: bold; font-size: 24px;   
        display: flex; justify-content: space-between; align-items: center;
        -webkit-print-color-adjust: exact; print-color-adjust: exact; line-height: 1.2;
    }

    .card-body { width: 100%; }
    
    .layout-table { width: 100%; border-collapse: collapse; border: none; margin: 0; padding: 0; table-layout: fixed; }
    
    /* BILDSPALTE: Jetzt 160px (ca. 4cm) */
    .layout-img-cell {
        width: 160px;
        min-width: 160px;
        max-width: 160px;
        vertical-align: top;
        padding: 0;
        border-right: 2px solid #999;
        background-color: #fff;
    }
    
    .player-img { 
        width: 100%; 
        height: auto;
        object-fit: cover; 
        display: block; 
    }
    
    .layout-stats-cell { vertical-align: top; padding: 0; width: auto; }
    
    /* STATS TABELLE */
    .stats-table { width: 100%; border-collapse: collapse; font-size: 20px; text-align: center; color: black; }
    
    .stats-table th, .stats-table td { 
        border: 1px solid #999; 
        padding: 5px 2px; /* Wenig Padding horizontal, um Platz zu sparen */      
        vertical-align: middle;
    }
    
    .stats-table th { font-size: 18px; background-color: #f0f0f0; }

    .bg-gray { background-color: #f0f0f0; -webkit-print-color-adjust: exact; }
    .font-bold { font-weight: bold; font-size: 22px; } /* Zahlen riesig */
    
    /* --- NOTIZEN DESIGN --- */
    .note-row td { 
        height: 40px;           /* Viel Platz zum Schreiben */
        text-align: left; 
        padding-left: 10px;
        font-size: 20px;
        vertical-align: bottom; 
        border: none;           
        border-bottom: 2px dashed #666; /* Dickere Linie */
        color: #333;            
    }
    
    .note-row td:first-child { border-left: none; }
    .note-row td:last-child { border-right: none; }

    /* Die Farbe wird jetzt per Inline-Style erzwungen (src/html_gen.py), 
       aber der Rahmen bleibt hier definiert */
    .note-right { 
        border-left: 3px solid #999 !important; 
        -webkit-print-color-adjust: exact; 
    }

    .team-stats-container { margin-top: 30px; page-break-inside: avoid; }
    
    @media print {
        body { -webkit-print-color-adjust: exact; }
        .no-print { display: none; }
    }
</style>
"""

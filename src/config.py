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
# ... andere Konfigurationen in src/config.py

# Beispiel CSS_STYLES - PASSEN SIE DIESEN BEREICH IN IHRER DATEI AN!
CSS_STYLES = """
    <style>
        body {
            font-family: Arial, sans-serif;
            font-size: 14pt; /* GRUNDSCHRIFTGRÖSSE FÜR PDF ANPASSEN */
        }
        h1, h2, h3, h4 {
            color: #333;
            margin-bottom: 0.5em;
        }
        /* Player Card Adjustments */
        .player-card {
            border: 1px solid #ccc;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
            display: flex;
            align-items: flex-start;
            page-break-inside: avoid;
        }
        .player-card-image {
            width: 100px;
            height: 100px;
            border-radius: 50%;
            object-fit: cover;
            margin-right: 15px;
            flex-shrink: 0;
        }
        .player-info h3 {
            margin-top: 0;
            margin-bottom: 5px;
            font-size: 18pt; /* Überschrift Spielername */
        }
        .player-info p {
            margin: 0;
            font-size: 12pt; /* Spieler Details wie Größe, Position */
        }
        .player-stats table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        .player-stats th, .player-stats td {
            border: 1px solid #ddd;
            padding: 5px;
            text-align: left;
            font-size: 10pt; /* Spieler Statistikwerte in der Tabelle */
        }
        .player-notes {
            margin-top: 10px;
            border-left: 3px solid;
            padding-left: 10px;
        }
        .player-notes div {
            font-size: 10pt; /* Notizen-Text */
        }

        /* Team Stats Table Adjustments */
        .team-stats-container table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        .team-stats-container th, .team-stats-container td {
            border: 1px solid #ddd;
            padding: 5px;
            text-align: left;
            font-size: 10pt; /* Team Statistikwerte in der Tabelle */
        }
        .team-stats-container th {
            background-color: #f2f2f2;
        }

        /* Allgemeine Sektionen */
        .custom-section h2 {
            font-size: 16pt; /* Überschrift der Custom Sections */
        }
        .custom-section ul {
            list-style-type: disc;
            margin-left: 20px;
        }
        .custom-section li {
            font-size: 12pt; /* Liste Text */
            margin-bottom: 5px;
        }
        
        /* HEADER/FOOTER (falls in html_gen.py genutzt, diese CSS-Klassen können angepasst werden) */
        .report-header {
            text-align: center;
            margin-bottom: 20px;
        }
        .report-header h1 {
            font-size: 24pt;
        }
        .report-header h2 {
            font-size: 18pt;
        }
        .report-header img {
            max-height: 80px;
            vertical-align: middle;
        }

        /* Page Breaks für PDF */
        .page-break-before {
            page-break-before: always;
        }
    </style>
"""

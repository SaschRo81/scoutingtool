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
# --- Inhalt für src/config.py, im Bereich der CSS_STYLES Variable ---

CSS_STYLES = """
    <style>
        body {
            font-family: Arial, sans-serif;
            font-size: 14pt; /* Grundschriftgröße für den gesamten Bericht, falls nicht spezifischer überschrieben */
            color: #333;
        }
        h1, h2, h3, h4 {
            color: #333;
            margin-bottom: 0.5em;
        }

        /* --- Spieler-Karten Details --- */
        .player-card {
            border: 1px solid #ccc;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
            display: flex;
            align-items: flex-start;
            page-break-inside: avoid; /* Verhindert das Umbrechen von Karten mitten im PDF */
            box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
        }
        .player-card-image {
            width: 120px; /* Bildgröße etwas erhöht */
            height: 120px; /* Bildgröße etwas erhöht */
            border-radius: 50%;
            object-fit: cover;
            margin-right: 20px;
            flex-shrink: 0;
            border: 2px solid #ddd;
        }
        .player-info h3 {
            margin-top: 0;
            margin-bottom: 5px;
            font-size: 20pt; /* Spielername deutlich größer */
            color: #003366;
        }
        .player-info p {
            margin: 0;
            font-size: 14pt; /* Spieler Details wie Größe, Position - größer */
            line-height: 1.4;
        }

        /* --- Spieler-Statistik-Tabelle innerhalb der Karte --- */
        .player-stats table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        .player-stats th, .player-stats td {
            border: 1px solid #ddd;
            padding: 8px; /* Padding erhöht */
            text-align: center; /* Werte zentriert */
            font-size: 12pt; /* Statistikwerte - größer */
        }
        .player-stats th {
            background-color: #e9ecef;
            font-weight: bold;
            color: #555;
        }
        .player-stats tr:nth-child(even) {
            background-color: #f9f9f9; /* Leichte Streifen für bessere Lesbarkeit */
        }

        /* --- Spieler-Notizen --- */
        .player-notes {
            margin-top: 15px;
            border-left: 5px solid; /* Dickere Leiste */
            padding-left: 15px;
            font-size: 14pt; /* Notizen-Text - deutlich größer */
            line-height: 1.6;
            color: #444;
        }
        .player-notes strong {
            color: #003366; /* Fokus-Titel in Notizen */
        }

        /* --- Team Statistik Tabelle (separate Tabelle) --- */
        .team-stats-container h2 {
            font-size: 20pt;
            color: #003366;
            margin-top: 30px;
        }
        .team-stats-container table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            font-size: 12pt; /* Team Statistikwerte in der Tabelle - größer */
        }
        .team-stats-container th, .team-stats-container td {
            border: 1px solid #ddd;
            padding: 10px; /* Padding erhöht */
            text-align: left;
        }
        .team-stats-container th {
            background-color: #003366;
            color: white;
            font-weight: bold;
        }
        .team-stats-container tr:nth-child(even) {
            background-color: #f2f7fc;
        }

        /* --- Custom Sections (Offense, Defense, About) --- */
        .custom-section h2 {
            font-size: 20pt; /* Überschrift der Custom Sections - größer */
            color: #003366;
            margin-top: 30px;
        }
        .custom-section ul {
            list-style-type: disc;
            margin-left: 25px;
            padding-left: 0;
        }
        .custom-section li {
            font-size: 14pt; /* Liste Text - größer */
            margin-bottom: 8px;
            line-height: 1.5;
        }
        .custom-section li strong {
            color: #0055aa;
        }
        .custom-section p {
            font-size: 14pt; /* Beschreibungstext - größer */
        }
        
        /* --- HEADER/FOOTER für den generierten HTML/PDF --- */
        .report-header-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 10px;
            border-bottom: 2px solid #003366;
            margin-bottom: 20px;
        }
        .report-header-logo {
            flex-shrink: 0;
            margin-right: 15px;
        }
        .report-header-logo img {
            max-height: 80px; /* Logo-Größe */
            vertical-align: middle;
        }
        .report-header-info {
            text-align: center;
            flex-grow: 1;
        }
        .report-header-info h1 {
            font-size: 28pt; /* Haupttitel des Berichts */
            margin: 0;
            color: #003366;
        }
        .report-header-info h2 {
            font-size: 20pt; /* Untertitel des Berichts */
            margin: 0;
            color: #555;
        }
        .report-header-meta {
            text-align: right;
            font-size: 12pt;
            color: #777;
            flex-shrink: 0;
            margin-left: 15px;
        }


        /* Page Breaks für PDF */
        .page-break-before {
            page-break-before: always;
        }
    </style>
"""

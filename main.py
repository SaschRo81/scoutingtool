# ganz oben
import streamlit as st
import pandas as pd
import requests
import base64
import datetime
from io import BytesIO
from PIL import Image

try:
    import pdfkit
    HAS_PDFKIT = True
except ImportError:
    HAS_PDFKIT = False


# --- VERSION & KONFIGURATION ---
VERSION = "v2.9 (Logo Size Fix)"
st.set_page_config(page_title=f"DBBL Scouting {VERSION}", layout="wide", page_icon="🏀")

API_HEADERS = {
    "accept": "application/json",
    "X-API-Key": "48673298c840c12a1646b737c83e5e5e"
}
SEASON_ID = "2025"

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
    159: {"name": "Medikamente per Klick Bamberg Baskets", "staffel": "Süd"}
}

# --- SESSION STATE ---
if "print_mode" not in st.session_state:
    st.session_state.print_mode = False

if "final_html" not in st.session_state:
    st.session_state.final_html = ""   # leer initialisieren

if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None

if "roster_df" not in st.session_state:
    st.session_state.roster_df = None
if "team_stats" not in st.session_state:
    st.session_state.team_stats = None
if "game_meta" not in st.session_state:
    st.session_state.game_meta = {}
if "optimized_images" not in st.session_state:
    st.session_state.optimized_images = {}

if "saved_notes" not in st.session_state:
    st.session_state.saved_notes = {}
if "saved_colors" not in st.session_state:
    st.session_state.saved_colors = {}

if "facts_offense" not in st.session_state:
    st.session_state.facts_offense = pd.DataFrame(
        [{"Fokus": "Run", "Beschreibung": "fastbreaks & quick inbounds"}]
    )
if "facts_defense" not in st.session_state:
    st.session_state.facts_defense = pd.DataFrame(
        [{"Fokus": "Rebound", "Beschreibung": "box out!"}]
    )
if "facts_about" not in st.session_state:
    st.session_state.facts_about = pd.DataFrame(
        [{"Fokus": "Energy", "Beschreibung": "100% effort"}]
    )

# --- HILFSFUNKTIONEN ---

def get_logo_url(team_id):
    return f"https://api-s.dbbl.scb.world/images/teams/logo/{SEASON_ID}/{team_id}"

def format_minutes(val):
    try:
        v = float(val)
        if v <= 0:
            return "00:00"
        if v > 48:
            mins = int(v // 60)
            secs = int(v % 60)
        else:
            mins = int(v)
            secs = int((v % 1) * 60)
        return f"{mins:02d}:{secs:02d}"
    except:
        return "00:00"

def clean_pos(pos):
    if not pos or pd.isna(pos):
        return "-"
    return str(pos).replace("_", " ").title()

def optimize_image_base64(url):
    if url in st.session_state.optimized_images:
        return st.session_state.optimized_images[url]
    if not url or "placeholder" in url:
        return url
    try:
        response = requests.get(url, headers=API_HEADERS, timeout=3)
        if response.status_code == 200:
            img = Image.open(BytesIO(response.content))
            base_height = 150
            w_percent = base_height / float(img.size[1])
            w_size = int(float(img.size[0]) * float(w_percent))
            img = img.resize((w_size, base_height), Image.Resampling.LANCZOS)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=70)
            img_str = base64.b64encode(buffer.getvalue()).decode()
            final_src = f"data:image/jpeg;base64,{img_str}"
            st.session_state.optimized_images[url] = final_src
            return final_src
    except:
        pass
    return "https://via.placeholder.com/150?text=Err"

def get_player_metadata(player_id):
    try:
        url = f"https://api-s.dbbl.scb.world/season-players/{player_id}"
        resp = requests.get(url, headers=API_HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            raw_img = data.get("imageUrl", "")
            opt_img = optimize_image_base64(raw_img) if raw_img else ""
            return {
                "img": opt_img,
                "height": data.get("height", 0),
                "pos": data.get("position", "-"),
            }
    except:
        pass
    return {"img": "", "height": 0, "pos": "-"}

# --- HTML GENERATOREN (wie bei dir, unverändert bis auf max-width-Fix bei Bildern) ---

def generate_header_html(meta):
    return f"""
<div style="font-family: Arial, sans-serif; page-break-inside: avoid;">
    <div style="text-align: right; font-size: 10px; color: #888; border-bottom: 1px solid #eee; margin-bottom: 10px;">
        DBBL Scouting Pro by Sascha Rosanke
    </div>
    <div style="border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 30px; text-align: center;">
        <h1 style="margin: 0; padding: 0; font-size: 24px; color: #000; font-weight: bold;">Scouting Report | {meta['date']} - {meta['time']} Uhr</h1>
        <br>
        <div style="display: flex; align-items: center; justify-content: center; gap: 40px;">
            <div style="text-align: center;">
                <img src="{meta['home_logo']}" style="height: 50px; max-width: 150px; object-fit: contain;">
                <div style="font-weight: bold; margin-top: 5px; font-size: 16px;">{meta['home_name']}</div>
            </div>
            <div style="font-size: 24px; font-weight: bold; color: #333;">VS</div>
            <div style="text-align: center;">
                <img src="{meta['guest_logo']}" style="height: 50px; max-width: 150px; object-fit: contain;">
                <div style="font-weight: bold; margin-top: 5px; font-size: 16px;">{meta['guest_name']}</div>
            </div>
        </div>
    </div>
</div>
"""

# ... generate_top3_html, generate_card_html, generate_team_stats_html,
# generate_custom_sections_html bleiben genau wie in deinem Code,
# nur bei uploaded images unten max-width statt max_width:

# im Teil mit uploaded_files:
# html += f"<div style='margin-bottom:20px;'><img src='data:image/png;base64,{b64}' style='max-width:100%; border:1px solid #ccc;'></div>"

# --- ANSICHT: BEARBEITUNG ---
if not st.session_state.print_mode:
    st.title(f"🏀 DBBL Scouting Pro {VERSION}")

    st.subheader("1. Spieldaten")
    col_staffel, col_home, col_guest = st.columns([1, 2, 2])
    with col_staffel:
        staffel = st.radio("Staffel:", ["Süd", "Nord"], horizontal=True)
        teams_filtered = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == staffel}
        team_options = {v["name"]: k for k, v in teams_filtered.items()}
    with col_home:
        home_name = st.selectbox("Heim-Team:", list(team_options.keys()), index=0, key="sel_home")
        home_id = team_options[home_name]
        st.image(get_logo_url(home_id), width=100)
    with col_guest:
        guest_name = st.selectbox("Gast-Team:", list(team_options.keys()), index=1, key="sel_guest")
        guest_id = team_options[guest_name]
        st.image(get_logo_url(guest_id), width=100)

    st.write("---")
    scout_target = st.radio(
        "Wen möchtest du scouten?",
        ["Gastteam (Gegner)", "Heimteam"],
        horizontal=True,
        key="sel_target",
    )
    target_team_id = guest_id if scout_target == "Gastteam (Gegner)" else home_id

    col_date, col_time = st.columns(2)
    with col_date:
        date_input = st.date_input("Datum", datetime.date.today(), key="sel_date")
    with col_time:
        time_input = st.time_input("Tip-Off", datetime.time(16, 0), key="sel_time")

    st.divider()
    if st.button(f"2. Kader von {scout_target} laden", type="primary"):
        # ... dein API-Code unverändert ...
        pass  # hier nur verkürzt; nimm deinen bestehenden Block

    if st.session_state.roster_df is not None:
        st.subheader("3. Spieler auswählen")
        edited = st.data_editor(
            st.session_state.roster_df[["select", "NR", "NAME_FULL", "PPG", "TOT"]],
            column_config={"select": st.column_config.CheckboxColumn("Scout?", default=False)},
            disabled=["NR", "NAME_FULL", "PPG", "TOT"],
            hide_index=True,
        )
        selected_indices = edited[edited["select"]].index
        if len(selected_indices) > 0:
            st.divider()
            st.subheader("4. Notizen & Key Facts")

            with st.form("scouting_form"):
    st.write("**Spieler-Notizen:**")
    selection = st.session_state.roster_df.loc[selected_indices]
    form_results = []

    for _, row in selection.iterrows():
        pid = row['PLAYER_ID']
        c_h, c_c = st.columns([3, 1])
        c_h.markdown(f"##### #{row['NR']} {row['NAME_FULL']}")
        saved_c = st.session_state.saved_colors.get(pid, "Grau")
        try:
            idx = ["Grau", "Grün", "Rot"].index(saved_c)
        except:
            idx = 0

        col_opt = c_c.selectbox(
            "Markierung",
            ["Grau", "Grün", "Rot"],
            key=f"col_{pid}",
            index=idx,
            label_visibility="collapsed"
        )

        c1, c2 = st.columns(2)

        l1v = st.session_state.saved_notes.get(f"l1_{pid}", "")
        l2v = st.session_state.saved_notes.get(f"l2_{pid}", "")
        l3v = st.session_state.saved_notes.get(f"l3_{pid}", "")
        l4v = st.session_state.saved_notes.get(f"l4_{pid}", "")
        r1v = st.session_state.saved_notes.get(f"r1_{pid}", "")
        r2v = st.session_state.saved_notes.get(f"r2_{pid}", "")
        r3v = st.session_state.saved_notes.get(f"r3_{pid}", "")
        r4v = st.session_state.saved_notes.get(f"r4_{pid}", "")

        l1 = c1.text_input("L1", value=l1v, key=f"l1_{pid}", label_visibility="collapsed")
        l2 = c1.text_input("L2", value=l2v, key=f"l2_{pid}", label_visibility="collapsed")
        l3 = c1.text_input("L3", value=l3v, key=f"l3_{pid}", label_visibility="collapsed")
        l4 = c1.text_input("L4", value=l4v, key=f"l4_{pid}", label_visibility="collapsed")

        r1 = c2.text_input("R1", value=r1v, key=f"r1_{pid}", label_visibility="collapsed")
        r2 = c2.text_input("R2", value=r2v, key=f"r2_{pid}", label_visibility="collapsed")
        r3 = c2.text_input("R3", value=r3v, key=f"r3_{pid}", label_visibility="collapsed")
        r4 = c2.text_input("R4", value=r4v, key=f"r4_{pid}", label_visibility="collapsed")

        st.divider()

        form_results.append({
            "row": row,
            "pid": pid,
            "color": col_opt,
            "notes": {
                "l1": l1, "l2": l2, "l3": l3, "l4": l4,
                "r1": r1, "r2": r2, "r3": r3, "r4": r4
            }
        })

    st.markdown("### Key Facts")
    c_k1, c_k2, c_k3 = st.columns(3)
    with c_k1:
        st.caption("Offense")
        edited_off = st.data_editor(st.session_state.facts_offense, num_rows="dynamic", hide_index=True)
    with c_k2:
        st.caption("Defense")
        edited_def = st.data_editor(st.session_state.facts_defense, num_rows="dynamic", hide_index=True)
    with c_k3:
        st.caption("All About Us")
        edited_abt = st.data_editor(st.session_state.facts_about, num_rows="dynamic", hide_index=True)

    st.markdown("### Grafiken")
    uploaded_files = st.file_uploader(
        "Upload",
        accept_multiple_files=True,
        type=["png", "jpg", "jpeg"]
    )

    # ✅ WICHTIG: Diese Zeile ist korrekt eingerückt
    submitted = st.form_submit_button(
        "Speichern & PDF Generieren",
        type="primary"
    )


                # ... dein Form-Code für Spieler-Notizen, Facts & Uploads ...

               submitted = st.form_submit_button("Speichern & PDF Generieren", type="primary")

if submitted:
    # ... du baust hier dein HTML:
    html = generate_header_html(st.session_state.game_meta)
    html += generate_top3_html(st.session_state.roster_df)
    # + Karten, Teamstats, Grafiken, Custom Sections ...
    st.session_state.final_html = html

    if HAS_PDFKIT:
        full_html = f"""
        <html>
        <head>
        <meta charset="utf-8">
        <style>
        @page {{
            size: A4 portrait;
            margin: 10mm;
        }}
        body {{
            font-family: Arial, sans-serif;
        }}
        img {{
            max-width: 100%;
        }}
        </style>
        </head>
        <body>
        {st.session_state.final_html}
        </body>
        </html>
        """

        # falls nötig mit config:
        # config = pdfkit.configuration(wkhtmltopdf="/usr/bin/wkhtmltopdf")
        # st.session_state.pdf_bytes = pdfkit.from_string(full_html, False, configuration=config)
        st.session_state.pdf_bytes = pdfkit.from_string(full_html, False)
    else:
        st.session_state.pdf_bytes = None

    st.session_state.print_mode = True
    st.experimental_rerun()


# --- ANSICHT: PDF / DRUCK ---
else:
    if st.button("⬅️ Zurück"):
        st.session_state.print_mode = False
        st.experimental_rerun()

    if st.session_state.pdf_bytes:
        st.download_button(
            "📄 Scouting-Report als PDF herunterladen",
            data=st.session_state.pdf_bytes,
            file_name="scouting_report.pdf",
            mime="application/pdf",
        )
    else:
        if HAS_PDFKIT:
            st.warning("Es liegt noch kein PDF vor. Bitte Report neu generieren.")
        else:
            st.info("PDF-Erzeugung ist in dieser Umgebung nicht verfügbar (pdfkit fehlt).")

    st.markdown(st.session_state.final_html, unsafe_allow_html=True)


import streamlit as st
import pandas as pd
import datetime
import base64

# Externe Imports prüfen
try:
    import pdfkit
    HAS_PDFKIT = True
except ImportError:
    HAS_PDFKIT = False

# Module aus SRC
from src.config import VERSION, TEAMS_DB, SEASON_ID, CSS_STYLES
from src.utils import get_logo_url, optimize_image_base64
from src.utils import get_logo_url
from src.api import fetch_team_data, get_player_metadata_cached
from src.html_gen import (
    generate_header_html, generate_top3_html, generate_card_html, 
    generate_team_stats_html, generate_custom_sections_html
)

st.set_page_config(page_title=f"DBBL Scouting {VERSION}", layout="wide", page_icon="🏀")

# --- SESSION STATE ---
for key, default in [
    ("print_mode", False), ("final_html", ""), ("pdf_bytes", None),
    ("roster_df", None), ("team_stats", None), ("game_meta", {}),
    ("report_filename", "scouting_report.pdf"), ("saved_notes", {}), ("saved_colors", {}),
    ("facts_offense", pd.DataFrame([{"Fokus": "Run", "Beschreibung": "fastbreaks & quick inbounds"}])),
    ("facts_defense", pd.DataFrame([{"Fokus": "Rebound", "Beschreibung": "box out!"}])),
    ("facts_about", pd.DataFrame([{"Fokus": "Energy", "Beschreibung": "100% effort"}]))
]:
    if key not in st.session_state: st.session_state[key] = default

# --- ANSICHT: BEARBEITUNG ---
if not st.session_state.print_mode:
    st.title(f"🏀 DBBL Scouting Pro {VERSION}")

    # 1. SETUP
    st.subheader("1. Spieldaten")
    col_staffel, col_home, col_guest = st.columns([1, 2, 2])
    with col_staffel:
        staffel = st.radio("Staffel:", ["Süd", "Nord"], horizontal=True)
        teams_filtered = {k: v for k, v in TEAMS_DB.items() if v["staffel"] == staffel}
        team_options = {v["name"]: k for k, v in teams_filtered.items()}
    with col_home:
        home_name = st.selectbox("Heim:", list(team_options.keys()), index=0, key="sel_home")
        home_id = team_options[home_name]
        st.image(get_logo_url(home_id, SEASON_ID), width=80)
    with col_guest:
        guest_name = st.selectbox("Gast:", list(team_options.keys()), index=1, key="sel_guest")
        guest_id = team_options[guest_name]
        st.image(get_logo_url(guest_id, SEASON_ID), width=80)

    st.write("---")
    scout_target = st.radio("Target:", ["Gastteam (Gegner)", "Heimteam"], horizontal=True, key="sel_target")
    target_team_id = guest_id if scout_target == "Gastteam (Gegner)" else home_id
    
    c_d, c_t = st.columns(2)
    date_input = c_d.date_input("Datum", datetime.date.today())
    time_input = c_t.time_input("Tip-Off", datetime.time(16,0))

    # 2. LOAD DATA
    st.divider()
    # ...
    if st.button(f"2. Kader von {scout_target} laden", type="primary"):
        with st.spinner("Lade API Daten..."):
            df, ts = fetch_team_data(target_team_id, SEASON_ID)
            if df is not None:
                st.session_state.roster_df = df
                st.session_state.team_stats = ts
                
                # --- HIER IST DIE ÄNDERUNG ---
                # Wir wandeln die URLs direkt in Base64 um, damit pdfkit kein Internet braucht
                home_logo_url = get_logo_url(home_id, SEASON_ID)
                guest_logo_url = get_logo_url(guest_id, SEASON_ID)
                
                st.session_state.game_meta = {
                    "home_name": home_name, 
                    "home_logo": optimize_image_base64(home_logo_url), # <--- Umwandeln!
                    "guest_name": guest_name, 
                    "guest_logo": optimize_image_base64(guest_logo_url), # <--- Umwandeln!
                    "date": date_input.strftime("%d.%m.%Y"), 
                    "time": time_input.strftime("%H:%M")
                }
                # -----------------------------
            else:
                st.error("Fehler beim Laden der Daten.")

   # ... (Code davor bleibt gleich) ...

    # 3. SELECT & EDIT
    if st.session_state.roster_df is not None:
        st.subheader("3. Auswahl & Notizen")
        
        # Konfiguration der Spalten für bessere Lesbarkeit
        col_config = {
            "select": st.column_config.CheckboxColumn(
                "Auswahl",
                default=False,
                width="small" 
            ),
            "NR": st.column_config.TextColumn("#", width="small"),
            "NAME_FULL": st.column_config.TextColumn("Name"),
            "GP": st.column_config.NumberColumn("Spiele", format="%d"), # Spiele (GP)
            "PPG": st.column_config.NumberColumn("PPG", format="%.1f"),
            "FG%": st.column_config.NumberColumn("FG%", format="%.1f %%"), # Wurfquote
            "TOT": st.column_config.NumberColumn("REB", format="%.1f", help="Total Rebounds") # TOT als REB angezeigt
        }

        # HIER GEÄNDERT: Neue Spalten GP und FG% hinzugefügt
        # use_container_width=True macht die Tabelle breiter und leichter zu bedienen
        edited = st.data_editor(
            st.session_state.roster_df[["select", "NR", "NAME_FULL", "GP", "PPG", "FG%", "TOT"]], 
            column_config=col_config,
            disabled=["NR", "NAME_FULL", "GP", "PPG", "FG%", "TOT"], 
            hide_index=True,
            use_container_width=True 
        )
        
        selected_indices = edited[edited["select"]].index

        if len(selected_indices) > 0:
            st.divider()
            with st.form("scouting_form"):
    
    # ... (Rest des Codes bleibt gleich) ...
                selection = st.session_state.roster_df.loc[selected_indices]
                form_results = []
                
                for _, row in selection.iterrows():
                    pid = row["PLAYER_ID"]
                    c_h, c_c = st.columns([3, 1])
                    c_h.markdown(f"**#{row['NR']} {row['NAME_FULL']}**")
                    saved_c = st.session_state.saved_colors.get(pid, "Grau")
                    idx = ["Grau", "Grün", "Rot"].index(saved_c) if saved_c in ["Grau", "Grün", "Rot"] else 0
                    col_opt = c_c.selectbox("Farbe", ["Grau", "Grün", "Rot"], key=f"c_{pid}", index=idx, label_visibility="collapsed")
                    
                    c1, c2 = st.columns(2)
                    notes = {}
                    for k in ["l1", "l2", "l3", "l4", "r1", "r2", "r3", "r4"]:
                        val = st.session_state.saved_notes.get(f"{k}_{pid}", "")
                        box = c1 if k.startswith("l") else c2
                        notes[k] = box.text_input(k, value=val, key=f"{k}_{pid}", label_visibility="collapsed")
                    st.divider()
                    form_results.append({"row": row, "pid": pid, "color": col_opt, "notes": notes})

                # Key Facts
                c1, c2, c3 = st.columns(3)
                with c1: st.caption("Offense"); e_off = st.data_editor(st.session_state.facts_offense, num_rows="dynamic", hide_index=True)
                with c2: st.caption("Defense"); e_def = st.data_editor(st.session_state.facts_defense, num_rows="dynamic", hide_index=True)
                with c3: st.caption("About"); e_abt = st.data_editor(st.session_state.facts_about, num_rows="dynamic", hide_index=True)
                
                up_files = st.file_uploader("Plays Upload", accept_multiple_files=True, type=["png","jpg"])
                submitted = st.form_submit_button("Speichern & Generieren", type="primary")

            if submitted:
                # Save State
                st.session_state.facts_offense = e_off
                st.session_state.facts_defense = e_def
                st.session_state.facts_about = e_abt
                target_name = (guest_name if scout_target == "Gastteam (Gegner)" else home_name).replace(" ", "_")
                st.session_state.report_filename = f"Scout_{target_name}.pdf"
                
                for item in form_results:
                    st.session_state.saved_colors[item["pid"]] = item["color"]
                    for k, v in item["notes"].items(): st.session_state.saved_notes[f"{k}_{item['pid']}"] = v

                # Build HTML
                c_map = {"Grau": "#999999", "Grün": "#5c9c30", "Rot": "#d9534f"}
                html = generate_header_html(st.session_state.game_meta)
                html += generate_top3_html(st.session_state.roster_df)
                for item in form_results:
                    meta = get_player_metadata_cached(item["pid"])
                    html += generate_card_html(item["row"].to_dict(), meta, item["notes"], c_map[item["color"]])
                html += generate_team_stats_html(st.session_state.team_stats)
                if up_files:
                    # HIER GEÄNDERT: Neue Seite für Grafiken erzwingen
                    html += "<div style='page-break-before: always;'><h2>Plays & Grafiken</h2>"
                    
                    for f in up_files:
                        b64 = base64.b64encode(f.getvalue()).decode()
                        # Optional: max-height setzen, damit große Bilder nicht die Seite sprengen
                        html += f"<div style='margin-bottom:20px;'><img src='data:image/png;base64,{b64}' style='max-width:100%; max-height:900px; border:1px solid #ccc'></div>"
                    html += "</div>"
                html += generate_custom_sections_html(e_off, e_def, e_abt)
                st.session_state.final_html = html

                # Generate PDF
                # Generate PDF
                if HAS_PDFKIT:
                    try:
                        full = f"<!DOCTYPE html><html><head><meta charset='utf-8'>{CSS_STYLES}</head><body>{html}</body></html>"
                        
                        options = {
                            "page-size": "A4", 
                            "orientation": "Portrait",
                            "margin-top": "5mm", 
                            # "margin-right": "5mm", 
                            "margin-bottom": "5mm", 
                            # "margin-left": "5mm", 
                            "encoding": "UTF-8", 
                            
                            # HIER ÄNDERN:
                            # 0.44 gleicht das breitere Bild aus
                            "zoom": "0.44",  
                            
                            "load-error-handling": "ignore",
                            "load-media-error-handling": "ignore",
                            "javascript-delay": "1000",
                        }
                        
                        st.session_state.pdf_bytes = pdfkit.from_string(full, False, options=options)
                        
                        # Rerun nur bei Erfolg
                        st.session_state.print_mode = True
                        st.rerun()

                    except Exception as e:
                        st.error(f"PDF Error: {e}")

else:
    # PRINT MODE
    c1, c2 = st.columns([1, 4])
    with c1:
        if st.button("⬅️ Zurück"):
            st.session_state.print_mode = False
            st.rerun()
    with c2:
        if st.session_state.pdf_bytes:
            st.download_button("📄 Download PDF", st.session_state.pdf_bytes, st.session_state.report_filename, "application/pdf")
        elif HAS_PDFKIT: st.warning("PDF Generierung fehlgeschlagen.")
        else: st.info("PDFKit nicht installiert.")
    
    st.markdown(CSS_STYLES + st.session_state.final_html, unsafe_allow_html=True)

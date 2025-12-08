import streamlit as st
import json
import pandas as pd
from io import BytesIO

def export_session_state():
    """Wandelt die wichtigen Session-Daten in JSON um."""
    data = {
        "saved_notes": st.session_state.get("saved_notes", {}),
        "saved_colors": st.session_state.get("saved_colors", {}),
        # Dataframes müssen zu JSON/Dict konvertiert werden
        "facts_offense": st.session_state.get("facts_offense", pd.DataFrame()).to_dict(orient="records"),
        "facts_defense": st.session_state.get("facts_defense", pd.DataFrame()).to_dict(orient="records"),
        "facts_about": st.session_state.get("facts_about", pd.DataFrame()).to_dict(orient="records"),
        # Metadaten (optional, damit man weiß, welches Spiel es war)
        "meta_home": st.session_state.get("game_meta", {}).get("home_name", ""),
        "meta_guest": st.session_state.get("game_meta", {}).get("guest_name", "")
    }
    return json.dumps(data, indent=4)

def load_session_state(uploaded_file):
    """Lädt JSON und schreibt es in den Session State."""
    try:
        data = json.load(uploaded_file)
        
        # 1. Notizen & Farben laden
        if "saved_notes" in data:
            st.session_state["saved_notes"] = data["saved_notes"]
        if "saved_colors" in data:
            st.session_state["saved_colors"] = data["saved_colors"]
            
        # 2. Key Facts laden (zurück zu DataFrames)
        if "facts_offense" in data:
            st.session_state["facts_offense"] = pd.DataFrame(data["facts_offense"])
        if "facts_defense" in data:
            st.session_state["facts_defense"] = pd.DataFrame(data["facts_defense"])
        if "facts_about" in data:
            st.session_state["facts_about"] = pd.DataFrame(data["facts_about"])
            
        return True, "Daten erfolgreich geladen!"
    except Exception as e:
        return False, f"Fehler beim Laden: {e}"

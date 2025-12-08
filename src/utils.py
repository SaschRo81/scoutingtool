import streamlit as st
import pandas as pd
import requests
import base64
from io import BytesIO
from PIL import Image
from src.config import API_HEADERS

# Grauer Platzhalter (Base64)
GRAY_BOX_B64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

def get_logo_url(team_id: int, season_id: str) -> str:
    return f"https://api-s.dbbl.scb.world/images/teams/logo/{season_id}/{team_id}"

def format_minutes(val):
    try:
        v = float(val)
        if v <= 0: return "00:00"
        if v > 48:
            mins = int(v // 60)
            secs = int(v % 60)
        else:
            mins = int(v)
            secs = int((v % 1) * 60)
        return f"{mins:02d}:{secs:02d}"
    except Exception:
        return "00:00"

def clean_pos(pos):
    if not pos or pd.isna(pos): return "-"
    return str(pos).replace("_", " ").title()

@st.cache_data(show_spinner=False)
def optimize_image_base64(url):
    if not url or "placeholder" in url:
        return GRAY_BOX_B64
    try:
        response = requests.get(url, headers=API_HEADERS, timeout=2)
        if response.status_code == 200:
            img = Image.open(BytesIO(response.content))
            
            # 1. Größe anpassen
            base_height = 300
            if img.size[1] > base_height:
                w_percent = base_height / float(img.size[1])
                w_size = int(float(img.size[0]) * float(w_percent))
                img = img.resize((w_size, base_height), Image.Resampling.LANCZOS)

            # 2. Format bestimmen (Transparenz erhalten!)
            buffer = BytesIO()
            
            # Wenn das Bild Transparenz hat (RGBA) oder Palette (P) ist -> PNG speichern
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                img.save(buffer, format="PNG")
                mime_type = "image/png"
            else:
                # Sonst als JPEG speichern (besser komprimiert für Fotos)
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(buffer, format="JPEG", quality=80)
                mime_type = "image/jpeg"

            img_str = base64.b64encode(buffer.getvalue()).decode()
            return f"data:{mime_type};base64,{img_str}"
            
    except Exception:
        pass
    return GRAY_BOX_B64

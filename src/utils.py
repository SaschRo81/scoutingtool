import streamlit as st
import pandas as pd
import requests
import base64
from io import BytesIO
from PIL import Image
from src.config import API_HEADERS

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
        return url
    try:
        response = requests.get(url, headers=API_HEADERS, timeout=3)
        if response.status_code == 200:
            img = Image.open(BytesIO(response.content))
            base_height = 500
            w_percent = base_height / float(img.size[1])
            w_size = int(float(img.size[0]) * float(w_percent))
            if img.size[1] > base_height:
                img = img.resize((w_size, base_height), Image.Resampling.LANCZOS)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=95)
            img_str = base64.b64encode(buffer.getvalue()).decode()
            return f"data:image/jpeg;base64,{img_str}"
    except Exception:
        pass
    return "https://via.placeholder.com/150?text=Err"

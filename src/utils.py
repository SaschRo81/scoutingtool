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

            # 2. TRICK: Transparenz durch Weiß ersetzen
            # Erstelle ein neues Bild mit weißem Hintergrund
            new_img = Image.new("RGB", img.size, (255, 255, 255))
            
            # Wenn das Originalbild Transparenz hat, klebe es drauf
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                # Alpha-Kanal als Maske nutzen
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                new_img.paste(img, mask=img.split()[3])
            else:
                new_img.paste(img)

            # 3. Als JPEG speichern (hat keine Transparenz -> also weißer Hintergrund)
            buffer = BytesIO()
            new_img.save(buffer, format="JPEG", quality=90)
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            # Immer als JPEG zurückgeben
            return f"data:image/jpeg;base64,{img_str}"
            
    except Exception:
        pass
    return GRAY_BOX_B64

# Übersetzer DE · EN · EL

Web-App fürs Handy: Text **sprechen oder tippen**, **sauber übersetzen**, **automatisch gegenprüfen** und direkt per **WhatsApp, Telegram** oder über das Teilen-Menü verschicken.

Sprachen: Deutsch, Englisch, Griechisch, in jede Richtung (DE→EN, DE→EL, EL→DE, EL→EN, EN→DE, EN→EL).

## So funktioniert es

1. Oben die Sprachen wählen (⇄ tauscht sie) und den Tonfall: Neutral, Locker (Du) oder Förmlich (Sie).
2. Auf das Mikrofon tippen und sprechen. Zum Beenden nochmal tippen. Oder einfach tippen.
3. Die App übersetzt und prüft die Übersetzung danach in einem zweiten, unabhängigen Durchgang:
   - **Rückübersetzung** in deine Ausgangssprache, damit du selbst gegenlesen kannst
   - **Hinweise** auf Fehler, Auslassungen oder falschen Tonfall
   - bei Bedarf ein **verbesserter Vorschlag**, den du mit einem Tipp übernimmst
4. Übersetzung bei Bedarf noch von Hand anpassen, dann **Teilen**, **WhatsApp**, **Telegram** oder **Kopieren**.

### Zwei Arten der Spracheingabe (Einstellungen)

| Modus | Wie | Wofür |
|---|---|---|
| **KI-Aufnahme** (Standard) | Nimmt Audio auf, bis du Stopp tippst, und lässt es danach von OpenAI erkennen | Längere Texte. Bricht bei Pausen **nicht** ab, das ist der Unterschied zu Google und DeepL. |
| **Live-Diktat** | Spracherkennung des Browsers, Text erscheint sofort | Kostenlos. Startet nach Pausen automatisch neu. Geht am besten in Chrome auf Android. |

Die Diktierfunktion der Handy-Tastatur (Mikrofon-Taste auf der Tastatur) funktioniert im Textfeld zusätzlich immer.

## Einrichtung (einmalig)

### 1. OpenAI API-Key

Unter https://platform.openai.com/api-keys einen neuen Key anlegen und in der App unter ⚙ Einstellungen eintragen.
Der Key wird nur auf dem Handy gespeichert (localStorage) und nur an `api.openai.com` geschickt.

Kosten: Eine Nachricht mit Übersetzung und Prüfung kostet etwa 0,1 bis 0,5 Cent. Eine Minute Sprachaufnahme liegt in derselben Größenordnung.

### 2. Online stellen (GitHub Pages, kostenlos)

1. Im Repository auf GitHub: **Settings → Pages**
2. Unter „Build and deployment“: Source **Deploy from a branch**, Branch **main** (oder diesen Branch), Ordner **/ (root)**, dann **Save**
3. Nach 1 bis 2 Minuten ist die App erreichbar unter
   **https://saschro81.github.io/scoutingtool/uebersetzer/**

Mikrofon-Zugriff geht nur über `https`. GitHub Pages liefert das automatisch.

### 3. Aufs Handy als App

- **Android (Chrome):** Seite öffnen → Menü ⋮ → **Zum Startbildschirm hinzufügen** / **App installieren**
- **iPhone (Safari):** Seite öffnen → Teilen-Symbol → **Zum Home-Bildschirm**

Danach startet der Übersetzer wie eine normale App im Vollbild.

## Technik

Reine Web-App ohne Server und ohne Build-Schritt:

- `index.html`, `style.css`, `app.js`: Oberfläche und Logik
- `manifest.webmanifest`, `sw.js`, `icons/`: Installation als App und Offline-Start
- Spracherkennung: OpenAI `gpt-transcribe` (`/v1/audio/transcriptions`)
- Übersetzung und Prüfung: OpenAI `gpt-6.1-sol` (`/v1/chat/completions`, JSON-Antwort)
- Beide Modelle lassen sich in den Einstellungen unter „Erweitert“ ändern, etwa auf ein günstigeres Modell.
- Verlauf: die letzten 30 Übersetzungen, nur lokal auf dem Gerät

Lokal testen: `cd uebersetzer && python3 -m http.server 8000`, dann http://localhost:8000 öffnen.

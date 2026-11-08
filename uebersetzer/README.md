# Rosanke Übersetzer (DE · EN · EL)

Ein Werkzeug von [Rosanke Web & Digital](https://rosanke.de), gestaltet im Corporate Design (Navy/Markenblau, Montserrat und Open Sans, lokal eingebunden).

**Direkt öffnen:** https://raw.githack.com/SaschRo81/scoutingtool/claude/live-translation-tool-hzs1zl/uebersetzer/index.html

Web-App fürs Handy: Text **sprechen oder tippen**, **sauber übersetzen**, **automatisch gegenprüfen** und direkt per **WhatsApp, Telegram** oder über das Teilen-Menü verschicken.

Sprachen: Deutsch, Englisch, Griechisch, in jede Richtung. Englisch gibt es als **English (UK)** (britische Schreibweise und Wörter, z. B. colour, organise, flat, mobile) und als **English (US)** (color, organize, apartment, cell phone). Standard ist UK. Die Gegenprüfung kontrolliert auch, dass die gewählte Variante durchgehend eingehalten wird.

**Übersetzungsdienste** (wählbar unter ⚙ Einstellungen):
- **Google Gemini**: kostenlos, ohne Kreditkarte, mit KI-Gegenprüfung
- **DeepL** (API Developer, 1 Mio. Zeichen frei): braucht einmalig eine kleine Weiterleitung, siehe [deepl-proxy/ANLEITUNG.md](deepl-proxy/ANLEITUNG.md). Mit zusätzlichem Gemini-Key prüft Gemini die DeepL-Übersetzung.
- **OpenAI**: kostenpflichtig

## So funktioniert es

1. Oben die Sprachen wählen (⇄ tauscht sie) und den Tonfall: Neutral, Locker (Du) oder Förmlich (Sie).
2. Auf das Mikrofon tippen und sprechen. Zum Beenden nochmal tippen. Oder einfach tippen.
3. Die App übersetzt und prüft die Übersetzung danach in einem zweiten, unabhängigen Durchgang:
   - **Rückübersetzung** in deine Ausgangssprache, damit du selbst gegenlesen kannst
   - **Hinweise** auf Fehler, Auslassungen oder falschen Tonfall
   - bei Bedarf ein **verbesserter Vorschlag**, den du mit einem Tipp übernimmst
4. Übersetzung bei Bedarf noch von Hand anpassen, dann **Teilen**, **WhatsApp**, **Telegram** oder **Kopieren**.

### Gesprächsmodus (live, zwei Personen)

Oben auf **Gespräch** umschalten. Links stellst du deine Sprache ein (**Ich**), rechts die des Gegenübers.

1. Wer spricht, tippt auf **seinen** Knopf (z. B. „Deutsch“ oder „Ελληνικά“) und redet los.
2. Das Gesprochene erscheint **sofort beim Sprechen**. Jeder fertige Satz wird direkt übersetzt, die Übersetzung baut sich Wort für Wort auf, meist innerhalb von ein bis zwei Sekunden.
3. Zum Wechseln tippt der andere einfach auf seinen Knopf. Zum Beenden nochmal auf den eigenen.
4. In jeder Sprechblase stehen Übersetzung (groß) und Original (klein), so wissen beide immer, was gesagt wurde.
5. Mit **Übersetzung vorlesen** liest das Handy die Übersetzung vor, sobald der Sprecher fertig ist. Damit das Mikrofon die Stimme nicht mithört, wird während eines Redebeitrags nicht vorgelesen.
6. **Kopieren** übernimmt das ganze Gespräch (Original und Übersetzung) in die Zwischenablage.

Technik: Die Spracherkennung läuft live über den Browser (am besten Chrome auf Android, Safari auf dem iPhone). Übersetzt wird mit dem schnellen Modell `gemini-3.5-flash-lite` im Streaming-Verfahren, die letzten Sätze gehen als Zusammenhang mit. Fehlt die Browser-Spracherkennung (z. B. Firefox), nimmt die App jeden Redebeitrag auf und übersetzt ihn nach dem Antippen, dann allerdings mit ein paar Sekunden Verzögerung.

### Zwei Arten der Spracheingabe (Einstellungen)

| Modus | Wie | Wofür |
|---|---|---|
| **KI-Aufnahme** (Standard) | Nimmt Audio auf, bis du Stopp tippst, und lässt es danach von der KI (Gemini oder OpenAI) erkennen | Längere Texte. Bricht bei Pausen **nicht** ab, das ist der Unterschied zu Google und DeepL. |
| **Live-Diktat** | Spracherkennung des Browsers, Text erscheint sofort | Kostenlos. Startet nach Pausen automatisch neu. Geht am besten in Chrome auf Android. |

Die Diktierfunktion der Handy-Tastatur (Mikrofon-Taste auf der Tastatur) funktioniert im Textfeld zusätzlich immer.

## Einrichtung (einmalig)

### 1. API-Key (kostenlos)

**Empfohlen: Google Gemini, kostenlos**

1. https://aistudio.google.com/apikey öffnen und mit einem Google-Konto anmelden
2. **API-Key erstellen** antippen (keine Kreditkarte, kein Abo)
3. Key in der App unter ⚙ Einstellungen → „Google Gemini – kostenlos“ eintragen

Der kostenlose Tarif hat Limits pro Minute und pro Tag. Für private Nachrichten reicht das locker. Ist das Hauptmodell (`gemini-3.8-flash`) gerade ausgelastet, wechselt die App automatisch auf das Ersatzmodell (`gemini-3.1-flash-lite`).
Hinweis: Im kostenlosen Tarif darf Google die Eingaben zur Verbesserung seiner Dienste verwenden. Für Vertrauliches besser den kostenpflichtigen Tarif oder OpenAI nehmen.

**Alternative: OpenAI (kostenpflichtig)**

Key unter https://platform.openai.com/api-keys anlegen und in den Einstellungen „OpenAI“ wählen. Kosten: etwa 0,1 bis 0,5 Cent pro Nachricht mit Prüfung.

Beide Keys werden nur auf dem Handy gespeichert (localStorage) und nur an den jeweiligen Anbieter geschickt.

**Warum nicht DeepL?** Die DeepL-API (Free: 500.000 Zeichen im Monat) lässt laut eigener Doku keine Aufrufe direkt aus dem Browser zu. Dafür bräuchte es einen eigenen kleinen Server als Zwischenstation. Außerdem kann DeepL weder Sprache erkennen noch eine Übersetzung inhaltlich prüfen.

### 2. Dauerhafte Adresse (GitHub Pages, kostenlos)

Der Link oben funktioniert sofort. Für eine eigene, dauerhafte Adresse:

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
- `manifest.json`, `sw.js`, `icons/`: Installation als App und Offline-Start
- `deepl-proxy/worker.js`: Cloudflare Worker als Weiterleitung zu DeepL (DeepL blockiert direkte Aufrufe aus dem Browser)
- **Gemini (Standard, kostenlos):** Spracherkennung, Übersetzung und Prüfung über `generateContent` mit `gemini-3.8-flash`, Ersatzmodell `gemini-3.1-flash-lite`. Lehnt Gemini das Aufnahmeformat ab, wandelt die App die Aufnahme in WAV um und schickt sie erneut.
- **OpenAI (optional):** Spracherkennung mit `gpt-transcribe`, Übersetzung und Prüfung mit `gpt-6.1-sol`
- Alle Modelle lassen sich in den Einstellungen unter „Erweitert“ ändern.
- Verlauf: die letzten 30 Übersetzungen, nur lokal auf dem Gerät

Lokal testen: `cd uebersetzer && python3 -m http.server 8000`, dann http://localhost:8000 öffnen.

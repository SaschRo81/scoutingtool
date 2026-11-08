# DeepL im Rosanke Übersetzer einrichten

DeepL lässt keine Aufrufe direkt aus einer Web-App zu. Deshalb braucht es eine kleine
**Weiterleitung**: einen Cloudflare Worker. Der ist kostenlos (100.000 Anfragen pro Tag)
und in etwa 5 Minuten eingerichtet. Du machst das nur einmal.

Dein DeepL-Key wird im Worker **nicht** gespeichert. Er bleibt auf deinem Handy und
wird bei jeder Übersetzung nur durchgereicht. Ohne Key kann also niemand den Worker nutzen.

---

## 1. DeepL-Key holen

1. https://www.deepl.com/pro-api öffnen und den Tarif **DeepL API Developer** (kostenlos) wählen.
2. Konto anlegen. DeepL fragt dabei eventuell nach einer Kreditkarte zur Prüfung. Der
   Developer-Tarif kostet trotzdem nichts.
3. Unter **Konto → API-Keys** den Key kopieren. Kostenlose Keys enden auf `:fx`.

Der Developer-Tarif enthält **1 Million Zeichen**. Eine typische Nachricht hat 100–300
Zeichen, das reicht also für einige Tausend Nachrichten. Den Verbrauch zeigt die App unter
⚙ Einstellungen → „Verbindung & Kontingent prüfen“.

## 2. Cloudflare Worker anlegen

1. https://dash.cloudflare.com öffnen und kostenlos registrieren (keine Kreditkarte nötig).
2. Links **Workers & Pages** (je nach Ansicht auch „Compute → Workers“) → **Erstellen / Create**.
3. **„Mit Hello World beginnen“ / „Start with Hello World!“** wählen.
4. Als Namen z. B. `uebersetzer-deepl` eintragen → **Bereitstellen / Deploy**.
5. Danach **Code bearbeiten / Edit code** anklicken.
6. Den vorhandenen Code komplett löschen und den Inhalt der Datei
   [`worker.js`](worker.js) aus diesem Ordner einfügen.
   (Auf GitHub die Datei öffnen → Symbol „Copy raw file“ → einfügen.)
7. Rechts oben **Bereitstellen / Deploy**.
8. Die Adresse des Workers kopieren, sie sieht etwa so aus:
   `https://uebersetzer-deepl.DEINNAME.workers.dev`

**Test:** Die Adresse im Browser öffnen. Dort muss stehen:
`{"ok":true,"info":"DeepL-Weiterleitung für den Rosanke Übersetzer läuft."}`

### Optional: nur deine App zulassen

Im Worker unter **Settings → Variables and Secrets** eine Variable anlegen:

- Name: `ALLOWED_ORIGINS`
- Wert: `https://raw.githack.com,https://saschro81.github.io`

Dann nehmen nur noch diese Websites den Worker in Anspruch.

## 3. In der App eintragen

1. Übersetzer öffnen → ⚙ **Einstellungen**
2. Bei „KI-Dienst“ **DeepL** wählen
3. **DeepL API-Key** und **Adresse der DeepL-Weiterleitung** eintragen
4. **„Verbindung & Kontingent prüfen“** antippen. Dort sollte „✓ Verbindung klappt“ stehen.
5. **Speichern**

## Was DeepL kann und was nicht

| Funktion | mit DeepL |
|---|---|
| Übersetzen (Nachricht und Gespräch) | ✅ DeepL, inkl. UK/US-Englisch und Du/Sie (soweit DeepL das für die Sprache unterstützt) |
| Spracheingabe per **Live-Diktat** | ✅ läuft über den Browser, unabhängig von DeepL |
| Gegenprüfung | ✅ DeepL übersetzt zurück, du liest gegen. Mit zusätzlichem **Gemini-Key** prüft eine KI unabhängig auf Fehler und schlägt Verbesserungen vor. |
| **KI-Aufnahme** | ⚠️ DeepL kann keine Sprache erkennen. Dafür zusätzlich einen Gemini-Key eintragen oder „Live-Diktat“ nutzen. |

Hinweis zum Verbrauch: Die Rückübersetzung zur Gegenprüfung zählt ebenfalls als Zeichen.
Ist ein Gemini-Key eingetragen, prüft stattdessen Gemini, das spart DeepL-Zeichen.

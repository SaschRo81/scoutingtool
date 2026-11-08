/* DeepL-Weiterleitung für den Rosanke Übersetzer (Cloudflare Worker, kostenlos)
 *
 * DeepL erlaubt keine Aufrufe direkt aus dem Browser (CORS). Dieser Worker nimmt
 * die Anfrage der App entgegen, leitet sie an DeepL weiter und gibt die Antwort
 * mit den nötigen CORS-Headern zurück.
 *
 * Der DeepL-Key wird NICHT im Worker gespeichert. Er kommt bei jeder Anfrage aus
 * der App (Header "Authorization: DeepL-Auth-Key …") und wird nur durchgereicht.
 * Ohne eigenen Key kann also niemand über diesen Worker übersetzen.
 *
 * Optional: Unter Settings → Variables eine Variable ALLOWED_ORIGINS anlegen,
 * z. B. "https://raw.githack.com,https://saschro81.github.io". Dann nimmt der
 * Worker nur noch Anfragen von diesen Websites an. Ohne Variable: alle.
 */

const ALLOWED_PATHS = new Set(['/v2/translate', '/v2/usage', '/v2/languages']);

export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin') || '';
    const allowed = String(env.ALLOWED_ORIGINS || '*').split(',').map((s) => s.trim()).filter(Boolean);
    const originOk = allowed.includes('*') || allowed.includes(origin);

    const cors = {
      'Access-Control-Allow-Origin': originOk ? (origin || '*') : 'null',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Authorization, Content-Type',
      'Access-Control-Max-Age': '86400',
      Vary: 'Origin',
    };

    if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors });
    if (!originOk) return json({ message: 'Diese Website darf den Worker nicht nutzen.' }, 403, cors);

    const url = new URL(request.url);
    if (url.pathname === '/' || url.pathname === '') {
      return json({ ok: true, info: 'DeepL-Weiterleitung für den Rosanke Übersetzer läuft.' }, 200, cors);
    }
    if (!ALLOWED_PATHS.has(url.pathname)) return json({ message: 'Unbekannter Pfad.' }, 404, cors);
    if (request.method !== 'GET' && request.method !== 'POST') return json({ message: 'Methode nicht erlaubt.' }, 405, cors);

    const key = (request.headers.get('Authorization') || '').replace(/^DeepL-Auth-Key\s+/i, '').trim();
    if (!key) return json({ message: 'DeepL-Key fehlt.' }, 401, cors);

    // Kostenlose Keys (Developer/Free) enden auf ":fx" und laufen über api-free.deepl.com
    const host = key.endsWith(':fx') ? 'https://api-free.deepl.com' : 'https://api.deepl.com';

    let upstream;
    try {
      upstream = await fetch(host + url.pathname + url.search, {
        method: request.method,
        headers: {
          Authorization: 'DeepL-Auth-Key ' + key,
          'Content-Type': request.headers.get('Content-Type') || 'application/json',
          'User-Agent': 'Rosanke-Uebersetzer/1.0',
        },
        body: request.method === 'POST' ? await request.text() : undefined,
      });
    } catch {
      return json({ message: 'DeepL ist gerade nicht erreichbar.' }, 502, cors);
    }

    const headers = new Headers(cors);
    headers.set('Content-Type', upstream.headers.get('Content-Type') || 'application/json');
    const trace = upstream.headers.get('X-Trace-ID');
    if (trace) headers.set('X-Trace-ID', trace);
    return new Response(upstream.body, { status: upstream.status, headers });
  },
};

function json(obj, status, headers) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { ...headers, 'Content-Type': 'application/json; charset=utf-8' },
  });
}

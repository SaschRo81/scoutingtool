/* Übersetzer DE · EN · EL
 * Sprechen oder tippen → übersetzen → gegenprüfen → teilen.
 * Läuft komplett im Browser. Der OpenAI-Key liegt nur im localStorage dieses Geräts.
 */
(() => {
  'use strict';

  const API = 'https://api.openai.com/v1';
  const GEMINI_API = 'https://generativelanguage.googleapis.com/v1beta';
  const DEFAULTS = {
    provider: 'gemini', // 'gemini' (kostenlos) | 'openai'
    geminiModel: 'gemini-3.8-flash',
    geminiFallback: 'gemini-3.1-flash-lite',
    chatModel: 'gpt-6.1-sol',
    sttModel: 'gpt-transcribe',
    sttMode: 'ai',
    autoTranslate: true,
    src: 'de',
    tgt: 'el',
    style: 'neutral',
    withOriginal: false,
  };

  // iso = Sprachcode für die Spracherkennung, en = Beschreibung für die KI
  const LANGS = {
    de: { native: 'Deutsch', short: 'DE', iso: 'de', bcp: 'de-DE', en: 'German (standard German as used in Germany, correct use of ß and umlauts)' },
    'en-gb': { native: 'English (UK)', short: 'EN-UK', iso: 'en', bcp: 'en-GB',
      en: 'British English (UK spelling and vocabulary throughout, e.g. colour, organise, centre, travelled, flat, mobile, holiday; dates as 8 November)' },
    'en-us': { native: 'English (US)', short: 'EN-US', iso: 'en', bcp: 'en-US',
      en: 'American English (US spelling and vocabulary throughout, e.g. color, organize, center, traveled, apartment, cell phone, vacation; dates as November 8)' },
    el: { native: 'Ελληνικά', short: 'EL', iso: 'el', bcp: 'el-GR', en: 'Modern Greek (correct monotonic accents/tonos, final sigma ς, Greek question mark ;)' },
  };

  const STYLES = {
    neutral: 'neutral, friendly, natural everyday register',
    casual: 'informal and casual; address the reader informally (German "du", Greek singular "εσύ")',
    formal: 'polite and formal; address the reader formally (German "Sie", Greek polite plural "εσείς")',
  };

  // ---------- Speicher ----------
  const store = {
    get(key, fallback) {
      try {
        const v = localStorage.getItem('uebersetzer.' + key);
        return v === null ? fallback : JSON.parse(v);
      } catch { return fallback; }
    },
    set(key, value) {
      try { localStorage.setItem('uebersetzer.' + key, JSON.stringify(value)); } catch { /* privat-Modus */ }
    },
  };

  const settings = Object.assign({}, DEFAULTS, store.get('settings', {}));
  // ältere Einstellung "en" → britisches Englisch
  for (const k of ['src', 'tgt']) if (!LANGS[settings[k]]) settings[k] = settings[k] === 'en' ? 'en-gb' : DEFAULTS[k];
  if (settings.src === settings.tgt) settings.tgt = settings.src === 'de' ? 'el' : 'de';
  let apiKey = store.get('apiKey', '');        // OpenAI
  let geminiKey = store.get('geminiKey', '');  // Google Gemini
  const providerName = () => (settings.provider === 'openai' ? 'OpenAI' : 'Gemini');
  const hasKey = () => !!(settings.provider === 'openai' ? apiKey : geminiKey);
  const saveSettings = () => store.set('settings', settings);

  // ---------- DOM ----------
  const $ = (id) => document.getElementById(id);
  const el = {
    src: $('srcLang'), tgt: $('tgtLang'), swap: $('btnSwap'),
    srcLabel: $('srcLabel'), tgtLabel: $('tgtLabel'),
    srcText: $('srcText'), tgtText: $('tgtText'), interim: $('interim'),
    mic: $('btnMic'), recStatus: $('recStatus'), recHint: $('recHint'),
    clear: $('btnClear'), translate: $('btnTranslate'),
    resultCard: $('resultCard'), badge: $('checkBadge'), score: $('checkScore'),
    checkBody: $('checkBody'), backText: $('backText'), issues: $('issues'),
    improvedBox: $('improvedBox'), improvedText: $('improvedText'), applyImproved: $('btnApplyImproved'),
    withOriginal: $('withOriginal'),
    share: $('btnShare'), wa: $('btnWhatsApp'), tg: $('btnTelegram'), copy: $('btnCopy'), speak: $('btnSpeak'),
    dlgSettings: $('dlgSettings'), settingsForm: $('settingsForm'), btnSettings: $('btnSettings'),
    setKey: $('setKey'), setGeminiKey: $('setGeminiKey'), fieldOpenai: $('fieldOpenai'), fieldGemini: $('fieldGemini'),
    setGeminiModel: $('setGeminiModel'), setGeminiFallback: $('setGeminiFallback'), setAuto: $('setAuto'), setChatModel: $('setChatModel'), setSttModel: $('setSttModel'),
    resetModels: $('btnResetModels'),
    dlgHistory: $('dlgHistory'), btnHistory: $('btnHistory'), historyList: $('historyList'), clearHistory: $('btnClearHistory'),
    toast: $('toast'),
  };

  // ---------- Hilfsfunktionen ----------
  let toastTimer;
  function toast(msg, isError = false) {
    el.toast.textContent = msg;
    el.toast.classList.toggle('error', isError);
    el.toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.toast.classList.remove('show'), isError ? 5000 : 2200);
  }

  function fmtTime(sec) {
    const m = Math.floor(sec / 60), s = Math.floor(sec % 60);
    return `${m}:${String(s).padStart(2, '0')}`;
  }

  function appendText(textarea, add) {
    add = (add || '').trim();
    if (!add) return;
    const cur = textarea.value.replace(/\s+$/, '');
    textarea.value = cur ? cur + ' ' + add : add;
    textarea.dispatchEvent(new Event('input'));
  }

  function requireKey() {
    if (hasKey()) return true;
    toast(`Bitte zuerst den ${providerName()} API-Key eintragen.`, true);
    openSettings();
    return false;
  }

  class ApiError extends Error {
    constructor(status, message, provider = 'OpenAI') { super(message); this.status = status; this.provider = provider; }
  }

  function friendlyError(err) {
    if (err.name === 'AbortError') return 'Abgebrochen.';
    if (!navigator.onLine) return 'Keine Internetverbindung.';
    if (err instanceof ApiError) {
      const gem = err.provider === 'Gemini';
      if (err.status === 401 || err.status === 403 || (gem && err.status === 400 && /api key/i.test(err.message))) {
        return 'API-Key ungültig. Bitte in den Einstellungen prüfen.';
      }
      if (err.status === 429) {
        return gem
          ? 'Kostenloses Gemini-Kontingent gerade aufgebraucht. In einer Minute erneut versuchen (Tageslimit: morgen wieder).'
          : 'OpenAI-Limit erreicht oder kein Guthaben. Bitte später erneut versuchen.';
      }
      if (err.status === 404) return 'Modell nicht gefunden. Bitte in den Einstellungen unter „Erweitert“ prüfen.';
      return `${err.provider}-Fehler (${err.status}): ${err.message}`;
    }
    return 'Fehler: ' + (err.message || err);
  }

  async function apiFetch(path, init) {
    let res;
    try {
      res = await fetch(API + path, {
        ...init,
        headers: { Authorization: 'Bearer ' + apiKey, ...(init.headers || {}) },
      });
    } catch (e) {
      throw new Error('Verbindung zu OpenAI fehlgeschlagen.');
    }
    if (!res.ok) {
      let msg = res.statusText;
      try { msg = (await res.json()).error?.message || msg; } catch { /* kein JSON */ }
      throw new ApiError(res.status, msg);
    }
    return res.json();
  }

  function parseJsonLoose(text) {
    try { return JSON.parse(text); } catch { /* weiter */ }
    const m = String(text).match(/\{[\s\S]*\}/);
    if (m) { try { return JSON.parse(m[0]); } catch { /* weiter */ } }
    throw new Error('Antwort der KI konnte nicht gelesen werden.');
  }

  // Chat-Aufruf mit JSON-Antwort. Wenn ein Modell einen optionalen Parameter
  // nicht kennt (HTTP 400), wird einmal ohne die optionalen Parameter wiederholt.
  async function chatJson(system, user) {
    if (settings.provider !== 'openai') return geminiJson(system, user);
    const base = {
      model: settings.chatModel || DEFAULTS.chatModel,
      messages: [{ role: 'system', content: system }, { role: 'user', content: user }],
    };
    const attempts = [
      { ...base, response_format: { type: 'json_object' }, reasoning_effort: 'low' },
      { ...base, response_format: { type: 'json_object' } },
      base,
    ];
    let lastErr;
    for (const body of attempts) {
      try {
        const data = await apiFetch('/chat/completions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        return parseJsonLoose(data.choices?.[0]?.message?.content || '');
      } catch (e) {
        lastErr = e;
        if (!(e instanceof ApiError && e.status === 400)) throw e;
      }
    }
    throw lastErr;
  }

  // ---------- Google Gemini (kostenloser Tarif) ----------
  async function geminiCall(model, body) {
    let res;
    try {
      res = await fetch(`${GEMINI_API}/models/${encodeURIComponent(model)}:generateContent?key=${encodeURIComponent(geminiKey)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
    } catch {
      throw new Error('Verbindung zu Google Gemini fehlgeschlagen.');
    }
    if (!res.ok) {
      let msg = res.statusText;
      try { msg = (await res.json()).error?.message || msg; } catch { /* kein JSON */ }
      throw new ApiError(res.status, msg, 'Gemini');
    }
    const data = await res.json();
    const cand = data.candidates?.[0];
    const text = (cand?.content?.parts || []).filter((p) => p.text && !p.thought).map((p) => p.text).join('');
    if (!text) {
      if (data.promptFeedback?.blockReason || cand?.finishReason === 'SAFETY') throw new Error('Gemini hat die Anfrage abgelehnt.');
      return '';
    }
    return text;
  }

  // Erst das Hauptmodell, bei Limit/Überlast/unbekanntem Modell das Ersatzmodell.
  async function geminiGenerate(body) {
    const models = [...new Set([settings.geminiModel || DEFAULTS.geminiModel, settings.geminiFallback].filter(Boolean))];
    let lastErr;
    for (const m of models) {
      try {
        return await geminiCall(m, body);
      } catch (e) {
        lastErr = e;
        if (!(e instanceof ApiError && [404, 429, 500, 503].includes(e.status))) throw e;
      }
    }
    throw lastErr;
  }

  async function geminiJson(system, user) {
    const text = await geminiGenerate({
      systemInstruction: { parts: [{ text: system }] },
      contents: [{ role: 'user', parts: [{ text: user }] }],
      generationConfig: { responseMimeType: 'application/json' },
    });
    return parseJsonLoose(text);
  }

  function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve(String(r.result).split(',')[1] || '');
      r.onerror = () => reject(r.error);
      r.readAsDataURL(blob);
    });
  }

  // Wandelt eine Aufnahme in WAV (16 kHz, mono) um – Rückfall, falls Gemini das Originalformat ablehnt.
  async function toWav16k(blob) {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    const ctx = new Ctx();
    const audio = await new Promise((res, rej) => blob.arrayBuffer().then((buf) => ctx.decodeAudioData(buf, res, rej), rej));
    try { ctx.close(); } catch { /* egal */ }
    const rate = 16000;
    const off = new OfflineAudioContext(1, Math.max(1, Math.ceil(audio.duration * rate)), rate);
    const node = off.createBufferSource();
    node.buffer = audio;
    node.connect(off.destination);
    node.start();
    const pcm = (await off.startRendering()).getChannelData(0);
    const view = new DataView(new ArrayBuffer(44 + pcm.length * 2));
    const str = (o, t) => { for (let i = 0; i < t.length; i++) view.setUint8(o + i, t.charCodeAt(i)); };
    str(0, 'RIFF'); view.setUint32(4, 36 + pcm.length * 2, true); str(8, 'WAVE');
    str(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
    view.setUint32(24, rate, true); view.setUint32(28, rate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
    str(36, 'data'); view.setUint32(40, pcm.length * 2, true);
    for (let i = 0; i < pcm.length; i++) {
      const v = Math.max(-1, Math.min(1, pcm[i]));
      view.setInt16(44 + i * 2, v < 0 ? v * 0x8000 : v * 0x7fff, true);
    }
    return new Blob([view], { type: 'audio/wav' });
  }

  async function geminiTranscribe(blob) {
    if (blob.size > 14 * 1024 * 1024) throw new Error('Aufnahme zu lang. Bitte in mehreren Teilen aufnehmen.');
    const instruction = `Transcribe this audio word for word. Language: ${LANGS[settings.src].en}. `
      + 'Use correct punctuation, capitalization and accents. Output ONLY the transcript, no comments, no quotes. '
      + 'If there is no speech, output nothing.';
    const run = async (b) => (await geminiGenerate({
      contents: [{
        role: 'user',
        parts: [
          { text: instruction },
          { inlineData: { mimeType: b.type.split(';')[0] || 'audio/webm', data: await blobToBase64(b) } },
        ],
      }],
    })).trim();
    try {
      return await run(blob);
    } catch (e) {
      const formatProblem = e instanceof ApiError && e.status === 400 && !/api key/i.test(e.message);
      if (!formatProblem || blob.type.includes('wav')) throw e;
      return run(await toWav16k(blob));
    }
  }

  // ---------- Sprachen ----------
  function fillLangSelects() {
    for (const sel of [el.src, el.tgt]) {
      sel.innerHTML = '';
      for (const [code, l] of Object.entries(LANGS)) {
        const o = document.createElement('option');
        o.value = code;
        o.textContent = l.native;
        sel.appendChild(o);
      }
    }
    el.src.value = settings.src;
    el.tgt.value = settings.tgt;
    updateLangLabels();
  }

  function updateLangLabels() {
    el.srcLabel.textContent = LANGS[settings.src].native;
    el.tgtLabel.textContent = LANGS[settings.tgt].native;
    el.srcText.lang = settings.src;
    el.tgtText.lang = settings.tgt;
  }

  function setLangs(src, tgt) {
    if (src === tgt) tgt = Object.keys(LANGS).find((c) => c !== src);
    settings.src = src;
    settings.tgt = tgt;
    el.src.value = src;
    el.tgt.value = tgt;
    saveSettings();
    updateLangLabels();
  }

  el.src.addEventListener('change', () => {
    const src = el.src.value;
    let tgt = settings.tgt;
    if (src === tgt) tgt = settings.src; // tauschen
    setLangs(src, tgt);
  });
  el.tgt.addEventListener('change', () => {
    const tgt = el.tgt.value;
    let src = settings.src;
    if (src === tgt) src = settings.tgt;
    setLangs(src, tgt);
  });
  el.swap.addEventListener('click', () => {
    const translated = el.tgtText.value.trim();
    setLangs(settings.tgt, settings.src);
    if (translated && !el.resultCard.hidden) {
      el.srcText.value = translated;
      el.resultCard.hidden = true;
    }
  });

  // ---------- Tonfall ----------
  const chips = document.querySelectorAll('.chip');
  function renderChips() {
    chips.forEach((c) => c.setAttribute('aria-checked', String(c.dataset.style === settings.style)));
  }
  chips.forEach((c) => c.addEventListener('click', () => {
    settings.style = c.dataset.style;
    saveSettings();
    renderChips();
  }));

  // ---------- Spracheingabe ----------
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recState = 'idle'; // idle | recording | transcribing
  let activeMode = null; // 'ai' | 'browser' während einer Aufnahme
  let mediaRecorder, mediaStream, chunks = [], recStart = 0, recTimer, wakeLock;
  let recognition, keepListening = false;

  function setMicUi(state, status, hint = '') {
    recState = state;
    el.mic.classList.toggle('recording', state === 'recording');
    el.mic.classList.toggle('busy', state === 'transcribing');
    el.mic.setAttribute('aria-label', state === 'recording' ? 'Aufnahme beenden' : 'Aufnahme starten');
    el.recStatus.textContent = status;
    el.recHint.textContent = hint;
  }

  function idleHint() {
    if (settings.sttMode === 'browser') {
      return SR ? 'Live-Diktat · Text erscheint beim Sprechen' : 'Live-Diktat wird von diesem Browser nicht unterstützt';
    }
    return 'KI-Aufnahme · sprich in Ruhe, Pausen sind kein Problem';
  }
  const resetMicUi = () => { activeMode = null; setMicUi('idle', 'Tippen zum Sprechen', idleHint()); };

  async function keepAwake() {
    try { wakeLock = await navigator.wakeLock?.request('screen'); } catch { /* nicht unterstützt */ }
  }
  function releaseAwake() {
    try { wakeLock?.release(); } catch { /* egal */ }
    wakeLock = null;
  }

  el.mic.addEventListener('click', () => {
    if (recState === 'recording') return stopRecording();
    if (recState === 'transcribing') return;
    if (settings.sttMode === 'browser') startBrowserDictation();
    else startAiRecording();
  });

  // --- Modus 1: KI-Aufnahme (Audio aufnehmen, danach transkribieren) ---
  function pickMime() {
    const types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4;codecs=mp4a.40.2', 'audio/mp4', 'audio/ogg;codecs=opus'];
    if (!window.MediaRecorder) return '';
    return types.find((t) => MediaRecorder.isTypeSupported?.(t)) || '';
  }

  async function startAiRecording() {
    if (!requireKey()) return;
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      toast('Audioaufnahme wird von diesem Browser nicht unterstützt. Bitte Live-Diktat oder die Tastatur-Diktierfunktion nutzen.', true);
      return;
    }
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
    } catch (e) {
      toast('Kein Mikrofonzugriff. Bitte im Browser erlauben.', true);
      return;
    }
    const mime = pickMime();
    chunks = [];
    try {
      mediaRecorder = new MediaRecorder(mediaStream, mime ? { mimeType: mime, audioBitsPerSecond: 32000 } : undefined);
    } catch {
      mediaRecorder = new MediaRecorder(mediaStream);
    }
    mediaRecorder.ondataavailable = (ev) => { if (ev.data && ev.data.size) chunks.push(ev.data); };
    mediaRecorder.onstop = onAiRecordingStopped;
    mediaRecorder.start(1000);
    activeMode = 'ai';
    recStart = Date.now();
    keepAwake();
    setMicUi('recording', 'Aufnahme läuft · 0:00', 'Zum Beenden nochmal tippen');
    recTimer = setInterval(() => {
      el.recStatus.textContent = 'Aufnahme läuft · ' + fmtTime((Date.now() - recStart) / 1000);
    }, 500);
  }

  function stopRecording() {
    if (activeMode === 'browser') return stopBrowserDictation();
    clearInterval(recTimer);
    if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop();
  }

  async function onAiRecordingStopped() {
    mediaStream?.getTracks().forEach((t) => t.stop());
    releaseAwake();
    const type = mediaRecorder.mimeType || chunks[0]?.type || 'audio/webm';
    const blob = new Blob(chunks, { type });
    chunks = [];
    if (blob.size < 1500) {
      resetMicUi();
      toast('Aufnahme war zu kurz.', true);
      return;
    }
    setMicUi('transcribing', 'Text wird erkannt …', '');
    try {
      const text = await transcribe(blob);
      if (!text.trim()) {
        toast('Es wurde keine Sprache erkannt.', true);
      } else {
        appendText(el.srcText, text);
        if (settings.autoTranslate) runTranslation();
      }
    } catch (e) {
      toast(friendlyError(e), true);
    } finally {
      resetMicUi();
    }
  }

  function extFor(type) {
    if (type.includes('webm')) return 'webm';
    if (type.includes('mp4') || type.includes('aac') || type.includes('m4a')) return 'm4a';
    if (type.includes('ogg')) return 'ogg';
    if (type.includes('wav')) return 'wav';
    if (type.includes('mpeg')) return 'mp3';
    return 'webm';
  }

  async function transcribe(blob) {
    if (settings.provider !== 'openai') return geminiTranscribe(blob);
    const lang = LANGS[settings.src].iso;
    const model = settings.sttModel || DEFAULTS.sttModel;
    const prompt = {
      de: 'Diktierte Nachricht auf Deutsch, mit korrekter Groß-/Kleinschreibung und Satzzeichen.',
      en: 'Dictated message in English, with proper punctuation.',
      el: 'Υπαγορευμένο μήνυμα στα ελληνικά, με σωστή στίξη και τονισμό.',
    }[lang];
    const build = (withHints) => {
      const fd = new FormData();
      fd.append('file', blob, 'aufnahme.' + extFor(blob.type));
      fd.append('model', model);
      fd.append('response_format', 'json');
      if (withHints) {
        fd.append('prompt', prompt);
        if (/^(whisper|gpt-4o)/.test(model)) fd.append('language', lang);
      }
      return fd;
    };
    try {
      return (await apiFetch('/audio/transcriptions', { method: 'POST', body: build(true) })).text || '';
    } catch (e) {
      if (!(e instanceof ApiError && e.status === 400)) throw e;
      // Fallback: nur Pflichtfelder
      return (await apiFetch('/audio/transcriptions', { method: 'POST', body: build(false) })).text || '';
    }
  }

  // --- Modus 2: Live-Diktat über die Browser-Spracherkennung ---
  // Die Browser-Erkennung beendet sich bei Pausen selbst. Wir starten sie
  // dann sofort neu, solange der Nutzer nicht auf Stopp getippt hat.
  function startBrowserDictation() {
    if (!SR) {
      toast('Live-Diktat geht in diesem Browser nicht. In den Einstellungen „KI-Aufnahme“ wählen.', true);
      return;
    }
    keepListening = true;
    recognition = new SR();
    recognition.lang = LANGS[settings.src].bcp;
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onresult = (ev) => {
      let interim = '';
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const r = ev.results[i];
        if (r.isFinal) appendText(el.srcText, r[0].transcript);
        else interim += r[0].transcript;
      }
      el.interim.hidden = !interim;
      el.interim.textContent = interim;
    };
    recognition.onerror = (ev) => {
      if (ev.error === 'not-allowed' || ev.error === 'service-not-allowed') {
        keepListening = false;
        toast('Kein Mikrofonzugriff für das Live-Diktat.', true);
      } else if (ev.error === 'network') {
        keepListening = false;
        toast('Live-Diktat braucht eine Internetverbindung.', true);
      }
      // "no-speech" / "aborted" → einfach neu starten (onend)
    };
    recognition.onend = () => {
      if (keepListening) {
        try { recognition.start(); return; } catch { /* fällt durch */ }
      }
      finishBrowserDictation();
    };
    try {
      recognition.start();
    } catch (e) {
      keepListening = false;
      toast('Live-Diktat konnte nicht starten.', true);
      return;
    }
    keepAwake();
    activeMode = 'browser';
    recStart = Date.now();
    setMicUi('recording', 'Höre zu · 0:00', 'Zum Beenden nochmal tippen');
    recTimer = setInterval(() => {
      el.recStatus.textContent = 'Höre zu · ' + fmtTime((Date.now() - recStart) / 1000);
    }, 500);
  }

  function stopBrowserDictation() {
    keepListening = false;
    clearInterval(recTimer);
    try { recognition?.stop(); } catch { finishBrowserDictation(); }
  }

  function finishBrowserDictation() {
    clearInterval(recTimer);
    releaseAwake();
    // Restlichen Zwischenstand übernehmen, falls der letzte Satz nicht mehr final wurde
    if (!el.interim.hidden && el.interim.textContent) appendText(el.srcText, el.interim.textContent);
    el.interim.hidden = true;
    el.interim.textContent = '';
    const hadText = el.srcText.value.trim();
    resetMicUi();
    if (hadText && settings.autoTranslate && hasKey()) runTranslation();
  }

  // ---------- Übersetzen & Prüfen ----------
  let runId = 0;
  let lastResult = null;

  function translatePrompt(src, tgt, style) {
    return [
      `You are a professional human translator. Translate the user's message from ${LANGS[src].en} into ${LANGS[tgt].en}.`,
      'The source text was often dictated with speech recognition: silently fix obvious recognition mistakes, filler words and missing punctuation, but never add, drop or soften content.',
      'The result will be sent as a chat message (WhatsApp/Telegram), so it must read like it was written by a native speaker: natural, idiomatic, correct grammar, spelling and accents.',
      `Register: ${STYLES[style]}.`,
      `Write the target text strictly in ${LANGS[tgt].en}.`,
      'Keep names, numbers, dates, times, addresses, emojis and line breaks. Do not add greetings or comments.',
      'Answer ONLY with JSON: {"translation": "<the translated message>"}',
    ].join('\n');
  }

  function checkPrompt(src, tgt, style) {
    return [
      `You are a strict, independent bilingual reviewer (${LANGS[src].en} ↔ ${LANGS[tgt].en}).`,
      `You get an original message in ${LANGS[src].en} (possibly dictated, may contain speech-recognition errors) and its translation into ${LANGS[tgt].en}.`,
      `1. Translate the translation back into ${LANGS[src].en} as faithfully as possible, without looking at the original wording → "back_translation".`,
      '2. Compare meaning with the original: omissions, additions, wrong meaning, wrong numbers/dates/names, ambiguous phrasing, grammar or spelling errors, unnatural wording.',
      `3. Check the register (it should be ${STYLES[style]}) and that the translation consistently follows the conventions of ${LANGS[tgt].en}.`,
      '4. If anything should be changed, give a corrected full translation in "improved_translation", otherwise use "".',
      'Write "problem" and "suggestion" texts in German, short and concrete. Do not report pure matters of taste.',
      'Answer ONLY with JSON:',
      '{"back_translation": "...", "verdict": "ok" | "minor" | "major", "score": <integer 1-10>, "issues": [{"problem": "...", "suggestion": "..."}], "improved_translation": ""}',
    ].join('\n');
  }

  el.translate.addEventListener('click', runTranslation);

  async function runTranslation() {
    const text = el.srcText.value.trim();
    if (!text) { toast('Bitte zuerst Text sprechen oder eintippen.'); el.srcText.focus(); return; }
    if (!requireKey()) return;
    const { src, tgt, style } = settings;
    const id = ++runId;

    el.translate.disabled = true;
    el.translate.textContent = 'Übersetze …';
    el.resultCard.hidden = false;
    el.tgtText.value = '';
    el.tgtText.placeholder = 'Übersetzung wird erstellt …';
    setBadge('loading', 'Übersetze …');
    el.checkBody.hidden = true;
    el.score.textContent = '';

    try {
      const res = await chatJson(translatePrompt(src, tgt, style), text);
      if (id !== runId) return;
      const translation = String(res.translation || '').trim();
      if (!translation) throw new Error('Leere Übersetzung erhalten.');
      el.tgtText.value = translation;
      lastResult = { ts: Date.now(), src, tgt, style, text, translation };
      addHistory(lastResult);
      el.resultCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (e) {
      if (id !== runId) return;
      setBadge('bad', 'Fehlgeschlagen');
      el.tgtText.placeholder = '';
      toast(friendlyError(e), true);
      return;
    } finally {
      if (id === runId) {
        el.translate.disabled = false;
        el.translate.textContent = 'Übersetzen & prüfen';
      }
    }

    // Gegenprüfung in einem zweiten, unabhängigen Durchgang
    setBadge('loading', 'Wird gegengeprüft …');
    try {
      const chk = await chatJson(
        checkPrompt(src, tgt, style),
        `ORIGINAL (${LANGS[src].en}):\n${text}\n\nTRANSLATION (${LANGS[tgt].en}):\n${el.tgtText.value}`,
      );
      if (id !== runId) return;
      renderCheck(chk);
    } catch (e) {
      if (id !== runId) return;
      setBadge('warn', 'Prüfung nicht möglich');
      toast(friendlyError(e), true);
    }
  }

  function setBadge(kind, text) {
    el.badge.className = 'badge ' + (kind || '');
    el.badge.textContent = text;
  }

  function renderCheck(chk) {
    const issues = Array.isArray(chk.issues) ? chk.issues.filter((i) => i && (i.problem || i.suggestion)) : [];
    const improved = String(chk.improved_translation || '').trim();
    let verdict = String(chk.verdict || '').toLowerCase();
    if (!['ok', 'minor', 'major'].includes(verdict)) verdict = issues.length ? 'minor' : 'ok';

    if (verdict === 'ok') setBadge('ok', '✓ Passt');
    else if (verdict === 'minor') setBadge('warn', 'Kleine Hinweise');
    else setBadge('bad', 'Bitte prüfen');

    const score = Number(chk.score);
    el.score.textContent = score >= 1 && score <= 10 ? `Qualität ${Math.round(score)}/10` : '';

    el.backText.textContent = chk.back_translation || '–';
    el.issues.innerHTML = '';
    for (const i of issues) {
      const li = document.createElement('li');
      li.textContent = i.problem || '';
      if (i.suggestion) {
        const s = document.createElement('span');
        s.className = 'sugg';
        s.textContent = '→ ' + i.suggestion;
        li.appendChild(s);
      }
      el.issues.appendChild(li);
    }
    el.issues.hidden = !issues.length;

    const showImproved = improved && improved !== el.tgtText.value.trim();
    el.improvedBox.hidden = !showImproved;
    el.improvedText.textContent = improved;
    el.checkBody.hidden = false;
  }

  el.applyImproved.addEventListener('click', () => {
    el.tgtText.value = el.improvedText.textContent;
    el.improvedBox.hidden = true;
    setBadge('ok', '✓ Vorschlag übernommen');
    if (lastResult) { lastResult.translation = el.tgtText.value; updateLastHistory(lastResult); }
  });

  // ---------- Teilen ----------
  function shareText() {
    const t = el.tgtText.value.trim();
    if (!t) return '';
    if (!el.withOriginal.checked) return t;
    return `${t}\n\n— ${LANGS[settings.src].native} —\n${el.srcText.value.trim()}`;
  }

  function ensureText() {
    const t = shareText();
    if (!t) toast('Noch keine Übersetzung vorhanden.');
    return t;
  }

  el.withOriginal.checked = !!settings.withOriginal;
  el.withOriginal.addEventListener('change', () => { settings.withOriginal = el.withOriginal.checked; saveSettings(); });

  if (!navigator.share) el.share.hidden = true;

  el.share.addEventListener('click', async () => {
    const t = ensureText(); if (!t) return;
    try { await navigator.share({ text: t }); } catch (e) { if (e.name !== 'AbortError') copy(t); }
  });
  el.wa.addEventListener('click', () => {
    const t = ensureText(); if (!t) return;
    window.open('https://wa.me/?text=' + encodeURIComponent(t), '_blank', 'noopener');
  });
  el.tg.addEventListener('click', () => {
    const t = ensureText(); if (!t) return;
    // Telegram verlangt den Parameter "url"; der Text wird dort als Nachricht übernommen.
    window.open('https://t.me/share/url?url=' + encodeURIComponent(t), '_blank', 'noopener');
  });
  el.copy.addEventListener('click', () => { const t = ensureText(); if (t) copy(t); });

  async function copy(t) {
    try {
      await navigator.clipboard.writeText(t);
      toast('In die Zwischenablage kopiert');
    } catch {
      el.tgtText.select();
      document.execCommand('copy');
      toast('Kopiert');
    }
  }

  // Vorlesen (Kontrolle per Gehör)
  el.speak.addEventListener('click', () => {
    if (!window.speechSynthesis) { toast('Vorlesen wird nicht unterstützt.'); return; }
    if (speechSynthesis.speaking) { speechSynthesis.cancel(); return; }
    const t = el.tgtText.value.trim(); if (!t) return;
    const u = new SpeechSynthesisUtterance(t);
    u.lang = LANGS[settings.tgt].bcp;
    const voice = speechSynthesis.getVoices().find((v) => v.lang?.toLowerCase().startsWith(settings.tgt));
    if (voice) u.voice = voice;
    speechSynthesis.speak(u);
  });

  el.clear.addEventListener('click', () => {
    el.srcText.value = '';
    el.tgtText.value = '';
    el.resultCard.hidden = true;
    lastResult = null;
    runId++;
    el.srcText.focus();
  });

  // ---------- Verlauf ----------
  const HISTORY_MAX = 30;
  const getHistory = () => store.get('history', []);
  function addHistory(entry) {
    const h = getHistory();
    h.unshift(entry);
    store.set('history', h.slice(0, HISTORY_MAX));
  }
  function updateLastHistory(entry) {
    const h = getHistory();
    const i = h.findIndex((x) => x.ts === entry.ts);
    if (i >= 0) { h[i] = entry; store.set('history', h); }
  }
  function renderHistory() {
    const h = getHistory();
    el.historyList.innerHTML = '';
    if (!h.length) {
      const li = document.createElement('li');
      li.className = 'empty';
      li.textContent = 'Noch keine Übersetzungen.';
      el.historyList.appendChild(li);
      return;
    }
    for (const e of h) {
      const li = document.createElement('li');
      const meta = document.createElement('div');
      meta.className = 'h-meta';
      meta.textContent = `${new Date(e.ts).toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' })} · ${(LANGS[e.src] || {}).short || e.src} → ${(LANGS[e.tgt] || {}).short || e.tgt}`;
      const s = document.createElement('div'); s.className = 'h-src'; s.textContent = e.text;
      const t = document.createElement('div'); t.className = 'h-tgt'; t.textContent = e.translation;
      li.append(meta, s, t);
      li.addEventListener('click', () => {
        if (LANGS[e.src] && LANGS[e.tgt]) setLangs(e.src, e.tgt);
        if (e.style) { settings.style = e.style; saveSettings(); renderChips(); }
        el.srcText.value = e.text;
        el.tgtText.value = e.translation;
        el.resultCard.hidden = false;
        setBadge('', 'Aus dem Verlauf');
        el.score.textContent = '';
        el.checkBody.hidden = true;
        lastResult = e;
        el.dlgHistory.close();
      });
      el.historyList.appendChild(li);
    }
  }
  el.btnHistory.addEventListener('click', () => { renderHistory(); el.dlgHistory.showModal(); });
  el.clearHistory.addEventListener('click', () => {
    if (confirm('Gesamten Verlauf löschen?')) { store.set('history', []); renderHistory(); }
  });
  document.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', () => b.closest('dialog').close()));

  // ---------- Einstellungen ----------
  function showProviderFields(p) {
    el.fieldGemini.hidden = p === 'openai';
    el.fieldOpenai.hidden = p !== 'openai';
  }
  el.settingsForm.querySelectorAll('input[name=provider]').forEach((r) => r.addEventListener('change', () => showProviderFields(r.value)));

  function openSettings() {
    el.setKey.value = apiKey;
    el.setGeminiKey.value = geminiKey;
    el.setGeminiModel.value = settings.geminiModel;
    el.setGeminiFallback.value = settings.geminiFallback;
    el.settingsForm.querySelectorAll('input[name=provider]').forEach((r) => { r.checked = r.value === settings.provider; });
    showProviderFields(settings.provider);
    el.setAuto.checked = !!settings.autoTranslate;
    el.setChatModel.value = settings.chatModel;
    el.setSttModel.value = settings.sttModel;
    el.settingsForm.querySelectorAll('input[name=sttMode]').forEach((r) => { r.checked = r.value === settings.sttMode; });
    el.dlgSettings.showModal();
  }
  el.btnSettings.addEventListener('click', openSettings);
  el.resetModels.addEventListener('click', () => {
    el.setChatModel.value = DEFAULTS.chatModel;
    el.setSttModel.value = DEFAULTS.sttModel;
    el.setGeminiModel.value = DEFAULTS.geminiModel;
    el.setGeminiFallback.value = DEFAULTS.geminiFallback;
  });
  el.dlgSettings.addEventListener('close', () => {
    if (el.dlgSettings.returnValue !== 'save') return;
    apiKey = el.setKey.value.trim();
    store.set('apiKey', apiKey);
    geminiKey = el.setGeminiKey.value.trim();
    store.set('geminiKey', geminiKey);
    const prov = el.settingsForm.querySelector('input[name=provider]:checked');
    if (prov) settings.provider = prov.value;
    settings.geminiModel = el.setGeminiModel.value.trim() || DEFAULTS.geminiModel;
    settings.geminiFallback = el.setGeminiFallback.value.trim();
    settings.autoTranslate = el.setAuto.checked;
    settings.chatModel = el.setChatModel.value.trim() || DEFAULTS.chatModel;
    settings.sttModel = el.setSttModel.value.trim() || DEFAULTS.sttModel;
    const mode = el.settingsForm.querySelector('input[name=sttMode]:checked');
    if (mode) settings.sttMode = mode.value;
    saveSettings();
    if (recState === 'idle') resetMicUi();
    toast('Gespeichert');
  });

  // ---------- Start ----------
  fillLangSelects();
  renderChips();
  resetMicUi();
  if (!hasKey()) setTimeout(openSettings, 300);

  if ('serviceWorker' in navigator && location.protocol === 'https:') {
    navigator.serviceWorker.register('sw.js').catch(() => { /* offline-Cache optional */ });
  }
})();

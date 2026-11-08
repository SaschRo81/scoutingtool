/* Gesprächsmodus: zwei Personen, zwei Sprachen, Satz für Satz live übersetzt.
 * Spracherkennung läuft im Browser (Text erscheint beim Sprechen), jeder fertige
 * Satz wird sofort übersetzt und die Übersetzung erscheint Wort für Wort.
 */
(() => {
  'use strict';
  const U = window.Uebersetzer;
  if (!U) return;
  const { LANGS, settings } = U;
  const $ = (id) => document.getElementById(id);

  const log = $('talkLog');
  const empty = $('talkEmpty');
  const speakBox = $('talkSpeak');
  const btns = { me: $('talkMe'), other: $('talkOther') };

  const langOf = (who) => (who === 'me' ? settings.src : settings.tgt);
  const otherOf = (who) => (who === 'me' ? 'other' : 'me');

  // ---------- Ansicht umschalten ----------
  const tabs = document.querySelectorAll('.tab');
  function showView(view) {
    if (view === 'talk') U.stopDictation(); else stopTurn();
    tabs.forEach((t) => t.setAttribute('aria-selected', String(t.dataset.view === view)));
    $('viewMsg').hidden = view !== 'msg';
    $('viewTalk').hidden = view !== 'talk';
    document.body.classList.toggle('talk-mode', view === 'talk');
    settings.view = view;
    U.saveSettings();
  }
  tabs.forEach((t) => t.addEventListener('click', () => showView(t.dataset.view)));

  // ---------- Zustand ----------
  const entries = []; // { who, src, tgt, original, translation, status, el, spoken, retryable }
  let active = null;      // 'me' | 'other' | null
  let recog = null;       // laufende Browser-Spracherkennung
  let keep = false;       // nach Pausen automatisch weiterhören
  let interimText = '';
  let liveEl = null;
  let inflight = false;
  let recorder = null, stream = null, chunks = [];

  function renderButtons() {
    for (const who of ['me', 'other']) {
      const l = LANGS[langOf(who)];
      btns[who].querySelector('.tb-lang').textContent = l.native;
      btns[who].lang = l.iso;
    }
    updateButtonStates();
  }
  document.addEventListener('langs-changed', renderButtons);

  function updateButtonStates() {
    for (const who of ['me', 'other']) {
      const on = active === who;
      btns[who].classList.toggle('listening', on);
      btns[who].setAttribute('aria-pressed', String(on));
      btns[who].querySelector('.tb-state').textContent = on
        ? (U.SR ? 'Hört zu … tippen = fertig' : 'Nimmt auf … tippen = senden')
        : 'Tippen & sprechen';
    }
  }

  // ---------- Sprechblasen ----------
  function scrollDown() {
    requestAnimationFrame(() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' }));
  }

  function makeBubble(who, extra = '') {
    const d = document.createElement('div');
    d.className = `bubble ${who} ${extra}`;
    d.innerHTML = '<div class="b-meta"></div><div class="b-tr"></div><div class="b-or"></div>';
    empty.hidden = true;
    log.appendChild(d);
    if (liveEl && d !== liveEl) log.appendChild(liveEl); // Live-Blase bleibt unten
    return d;
  }

  function renderEntry(e) {
    const state = e.status === 'done' ? '' : e.status === 'error' ? 'error' : 'pending';
    e.el.className = `bubble ${e.who} ${state}`;
    e.el.querySelector('.b-meta').textContent = `${LANGS[e.src].short} → ${LANGS[e.tgt].short}`;
    const tr = e.el.querySelector('.b-tr');
    tr.lang = LANGS[e.tgt].iso;
    tr.textContent = e.status === 'error'
      ? (e.retryable ? 'Übersetzung fehlgeschlagen – zum Wiederholen tippen' : 'Übersetzung fehlgeschlagen')
      : e.translation;
    const or = e.el.querySelector('.b-or');
    or.lang = LANGS[e.src].iso;
    or.textContent = e.original;
  }

  function showLive(who, text) {
    if (!text) { liveEl?.remove(); liveEl = null; return; }
    if (!liveEl) liveEl = makeBubble(who, 'live');
    liveEl.className = `bubble ${who} live`;
    liveEl.querySelector('.b-meta').textContent = `${LANGS[langOf(who)].short} · spricht …`;
    liveEl.querySelector('.b-or').textContent = text;
    scrollDown();
  }

  // ---------- Sätze übersetzen ----------
  function addSegment(who, text) {
    text = (text || '').trim();
    if (!text) return;
    const last = entries[entries.length - 1];
    if (last && last.who === who && last.status === 'queued') {
      // Übersetzung des vorigen Satzes läuft noch → zusammenfassen (weniger Anfragen)
      last.original += ' ' + text;
      renderEntry(last);
    } else {
      const e = {
        who, src: langOf(who), tgt: langOf(otherOf(who)),
        original: text, translation: '', status: 'queued', spoken: false, retryable: true,
      };
      e.el = makeBubble(who);
      e.el.addEventListener('click', () => {
        if (e.status === 'error' && e.retryable) { e.status = 'queued'; renderEntry(e); pump(); }
      });
      entries.push(e);
      renderEntry(e);
    }
    scrollDown();
    pump();
  }

  function contextFor(e) {
    return entries
      .filter((x) => x !== e && x.status === 'done')
      .slice(-6)
      .map((x) => `${x.who === 'me' ? 'A' : 'B'} (${LANGS[x.src].short}): ${x.original}`)
      .join('\n');
  }

  async function pump() {
    if (inflight) return;
    const e = entries.find((x) => x.status === 'queued');
    if (!e) return;
    inflight = true;
    e.status = 'translating';
    renderEntry(e);
    try {
      const t = await U.streamTranslate(e.original, e.src, e.tgt, {
        context: contextFor(e),
        onDelta: (acc) => { e.translation = acc; e.el.querySelector('.b-tr').textContent = acc; },
      });
      e.translation = t || e.translation;
      e.status = e.translation ? 'done' : 'error';
    } catch (err) {
      e.status = 'error';
      U.toast(U.friendlyError(err), true);
    }
    renderEntry(e);
    inflight = false;
    scrollDown();
    maybeSpeak();
    pump();
  }

  // ---------- Vorlesen ----------
  speakBox.checked = !!settings.talkSpeak;
  speakBox.addEventListener('change', () => {
    settings.talkSpeak = speakBox.checked;
    U.saveSettings();
    if (!speakBox.checked) window.speechSynthesis?.cancel();
  });

  function pickVoice(code) {
    const voices = window.speechSynthesis.getVoices();
    const norm = (v) => (v.lang || '').toLowerCase().replace('_', '-');
    return voices.find((v) => norm(v) === LANGS[code].bcp.toLowerCase())
      || voices.find((v) => norm(v).startsWith(LANGS[code].iso));
  }

  // Vorgelesen wird erst, wenn gerade niemand spricht – sonst hört das Mikrofon mit.
  function maybeSpeak() {
    if (!speakBox.checked || !window.speechSynthesis || active) return;
    for (const e of entries) {
      if (e.spoken) continue;
      if (e.status === 'error') { e.spoken = true; continue; }
      if (e.status !== 'done') break; // Reihenfolge einhalten
      e.spoken = true;
      const u = new SpeechSynthesisUtterance(e.translation);
      u.lang = LANGS[e.tgt].bcp;
      const v = pickVoice(e.tgt);
      if (v) u.voice = v;
      window.speechSynthesis.speak(u);
    }
  }

  // ---------- Sprecherwechsel ----------
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));

  async function startTurn(who) {
    if (active === who) { stopTurn(); return; }
    const switching = !!active;
    if (switching) stopTurn();
    if (!U.requireKey()) return;
    window.speechSynthesis?.cancel();
    entries.forEach((e) => { if (e.status === 'done') e.spoken = true; }); // Altes nicht nachträglich vorlesen
    active = who;
    updateButtonStates();
    U.keepAwake();
    if (switching) await wait(150); // Android braucht kurz, bis die alte Erkennung frei ist
    if (active !== who) return;
    if (U.SR) startRecognition(who);
    else startRecorder(who);
  }

  function stopTurn() {
    const who = active;
    if (!who) return;
    keep = false;
    if (recog) {
      const r = recog;
      recog = null; // spätere Ergebnisse dieser Erkennung ignorieren
      if (interimText) addSegment(who, interimText);
      interimText = '';
      showLive(who, '');
      try { r.abort(); } catch { /* egal */ }
    }
    if (recorder && recorder.state !== 'inactive') recorder.stop();
    active = null;
    updateButtonStates();
    U.releaseAwake();
    maybeSpeak();
  }

  function startRecognition(who) {
    keep = true;
    interimText = '';
    const r = new U.SR();
    recog = r;
    r.lang = LANGS[langOf(who)].bcp;
    r.continuous = true;
    r.interimResults = true;
    r.maxAlternatives = 1;

    r.onresult = (ev) => {
      if (recog !== r) return;
      let interim = '';
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const res = ev.results[i];
        if (res.isFinal) addSegment(who, res[0].transcript);
        else interim += res[0].transcript;
      }
      interimText = interim;
      showLive(who, interim);
    };
    r.onerror = (ev) => {
      if (recog !== r) return;
      if (ev.error === 'not-allowed' || ev.error === 'service-not-allowed') {
        keep = false;
        U.toast('Kein Mikrofonzugriff. Bitte im Browser erlauben.', true);
      } else if (ev.error === 'network') {
        keep = false;
        U.toast('Die Spracherkennung braucht eine Internetverbindung.', true);
      }
      // "no-speech" / "aborted": onend startet neu
    };
    r.onend = () => {
      if (recog !== r) return;
      if (keep) {
        try { r.start(); return; } catch { /* fällt durch */ }
      }
      if (interimText) addSegment(who, interimText);
      interimText = '';
      showLive(who, '');
      recog = null;
      if (active === who) {
        active = null;
        updateButtonStates();
        U.releaseAwake();
        maybeSpeak();
      }
    };
    try {
      r.start();
    } catch {
      recog = null;
      active = null;
      updateButtonStates();
      U.toast('Spracherkennung konnte nicht starten.', true);
    }
  }

  // Rückfall für Browser ohne Spracherkennung: pro Redebeitrag aufnehmen und dann übersetzen
  async function startRecorder(who) {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      active = null;
      updateButtonStates();
      U.toast('Dieser Browser unterstützt keine Spracheingabe. Bitte Chrome oder Safari verwenden.', true);
      return;
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    } catch {
      active = null;
      updateButtonStates();
      U.toast('Kein Mikrofonzugriff. Bitte im Browser erlauben.', true);
      return;
    }
    const src = langOf(who), tgt = langOf(otherOf(who));
    const mime = U.pickMime();
    chunks = [];
    const rec = new MediaRecorder(stream, mime ? { mimeType: mime, audioBitsPerSecond: 32000 } : undefined);
    recorder = rec;
    const myStream = stream;
    rec.ondataavailable = (ev) => { if (ev.data && ev.data.size) chunks.push(ev.data); };
    rec.onstop = async () => {
      myStream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(chunks, { type: rec.mimeType || 'audio/webm' });
      chunks = [];
      if (blob.size < 1500) return;
      const e = { who, src, tgt, original: '…', translation: '', status: 'translating', spoken: false, retryable: false };
      e.el = makeBubble(who);
      entries.push(e);
      renderEntry(e);
      scrollDown();
      try {
        const res = await U.transcribeAndTranslate(blob, src, tgt, contextFor(e));
        if (!String(res.original || '').trim()) {
          e.el.remove();
          entries.splice(entries.indexOf(e), 1);
          if (!entries.length) empty.hidden = false;
          U.toast('Es wurde keine Sprache erkannt.');
          return;
        }
        e.original = res.original;
        e.translation = res.translation;
        e.status = e.translation ? 'done' : 'error';
      } catch (err) {
        e.status = 'error';
        U.toast(U.friendlyError(err), true);
      }
      renderEntry(e);
      scrollDown();
      maybeSpeak();
    };
    rec.start(1000);
  }

  btns.me.addEventListener('click', () => startTurn('me'));
  btns.other.addEventListener('click', () => startTurn('other'));

  // ---------- Kopieren / Leeren ----------
  $('talkCopy').addEventListener('click', async () => {
    const text = entries
      .filter((e) => e.status === 'done')
      .map((e) => `${LANGS[e.src].short}: ${e.original}\n${LANGS[e.tgt].short}: ${e.translation}`)
      .join('\n\n');
    if (!text) { U.toast('Noch nichts übersetzt.'); return; }
    try {
      await navigator.clipboard.writeText(text);
      U.toast('Gespräch kopiert');
    } catch {
      U.toast('Kopieren nicht möglich.', true);
    }
  });

  $('talkClear').addEventListener('click', () => {
    stopTurn();
    window.speechSynthesis?.cancel();
    entries.length = 0;
    log.querySelectorAll('.bubble').forEach((b) => b.remove());
    liveEl = null;
    empty.hidden = false;
  });

  // ---------- Start ----------
  renderButtons();
  showView(settings.view === 'talk' ? 'talk' : 'msg');
})();

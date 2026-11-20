"use strict";
const $ = id => document.getElementById(id);
const log = $("log"), status = $("status");
const session = localStorage.session || (localStorage.session = crypto.randomUUID());
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const setStatus = (t, err) => { status.textContent = t; status.classList.toggle("err", !!err); };
const opts = () => ({lang: $("lang").value || null, slow: $("slow").checked});

// ---------------------------------------------------------------- settings
for (const el of document.querySelectorAll(".phToggle")) {
  const key = "show_" + el.value;
  if (localStorage[key] === "0") el.checked = false;
  const apply = () => { document.body.classList.toggle("hide-" + el.value, !el.checked); localStorage[key] = el.checked ? "1" : "0"; };
  el.onchange = apply; apply();
}
for (const id of ["slow", "speakText"]) {
  $(id).checked = localStorage[id] === "1";
  $(id).onchange = () => localStorage[id] = $(id).checked ? "1" : "0";
}

// ---------------------------------------------------------------- audio
const queue = []; let playing = null;
function enqueue(src) { queue.push(src); if (!playing) next(); }
function next() {
  const src = queue.shift(); if (!src) { playing = null; return; }
  playing = new Audio(src); playing.onended = playing.onerror = next; playing.play().catch(next);
}
function stopAudio() { queue.length = 0; if (playing) { playing.pause(); playing = null; } }
async function speak(text, lang, slow) {
  const r = await fetch("/api/speak", {method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({text, lang, slow: slow ?? $("slow").checked})});
  if (!r.ok) return setStatus("Speech failed: " + r.status, true);
  stopAudio(); enqueue(URL.createObjectURL(await r.blob()));
}

// ---------------------------------------------------------------- chat rendering
function add(cls, html) {
  const d = document.createElement("div"); d.className = "msg " + cls; d.innerHTML = html;
  log.appendChild(d); log.scrollTop = log.scrollHeight; return d;
}
function phHtml(p) {
  let h = "";
  if (p.ipa) h += `<div class="ph ipa">/${esc(p.ipa)}/</div>`;
  if (p.romanized) h += `<div class="ph romanized">${esc(p.romanized)}</div>`;
  if (p.readable) h += `<div class="ph readable">${esc(p.readable)}</div>`;
  return h;
}
const sentHtml = sn => `<div class="sent"><div>${esc(sn.text)}</div>${phHtml(sn)}</div>`;
function botBubble() {
  const el = add("bot", `<div class="sents"></div><div class="typing"></div><div class="meta"></div>`);
  return {el, sents: el.querySelector(".sents"), typing: el.querySelector(".typing"), meta: el.querySelector(".meta"), pending: ""};
}
function finishBubble(b, reply, lang, langName) {
  b.typing.textContent = "";
  b.meta.innerHTML = `<span>${esc(langName)}</span><button class="small sec">Listen</button><button class="small sec">Slow</button><button class="small sec">Practise</button>`;
  const [listen, slow, prac] = b.meta.querySelectorAll("button");
  listen.onclick = () => speak(reply, lang, false);
  slow.onclick = () => speak(reply, lang, true);
  prac.onclick = () => { $("target").value = reply; $("lang").value = lang; showTab("practice"); annotateTarget(); };
}

// ---------------------------------------------------------------- streaming
async function streamTurn(url, init, onTranscript) {
  const b = {bubble: null};
  const res = await fetch(url, init);
  if (!res.ok) { setStatus(`Error ${res.status}: ${await res.text()}`, true); return; }
  const reader = res.body.getReader(), dec = new TextDecoder();
  let buf = "";
  const ensure = () => b.bubble || (b.bubble = botBubble());
  for (;;) {
    const {value, done} = await reader.read();
    if (done) break;
    buf += dec.decode(value, {stream: true});
    let i;
    while ((i = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, i); buf = buf.slice(i + 1);
      if (!line.trim()) continue;
      const ev = JSON.parse(line);
      if (ev.type === "error") { setStatus(ev.message, true); if (b.bubble) b.bubble.typing.textContent = ""; return; }
      if (ev.type === "transcript") { onTranscript?.(ev); setStatus("Thinking…"); }
      if (ev.type === "delta") { const x = ensure(); x.pending += ev.text; x.typing.textContent = x.pending; log.scrollTop = log.scrollHeight; }
      if (ev.type === "sentence") {
        const x = ensure();
        x.sents.insertAdjacentHTML("beforeend", sentHtml(ev));
        const k = x.pending.indexOf(ev.text);
        x.pending = k >= 0 ? x.pending.slice(k + ev.text.length).trimStart() : "";
        x.typing.textContent = x.pending;
        if (ev.audio_b64) { enqueue("data:audio/wav;base64," + ev.audio_b64); setStatus("Speaking…"); }
      }
      if (ev.type === "done") { const x = ensure(); finishBubble(x, ev.reply, ev.lang, ev.lang_name); setStatus("Ready."); }
    }
  }
}

async function sendText() {
  const text = $("text").value.trim(); if (!text) return;
  $("text").value = ""; add("user", esc(text)); setStatus("Thinking…"); stopAudio();
  await streamTurn("/api/stream/text", {method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({text, session, ...opts(), speak: $("speakText").checked})});
}
$("send").onclick = sendText;
$("text").onkeydown = e => { if (e.key === "Enter") sendText(); };

// ---------------------------------------------------------------- recorder (tap-to-talk with VAD, or hold)
let audioCtx = null;  // one shared context, resumed inside the user gesture
const sharedCtx = () => {
  audioCtx ||= new AudioContext();
  if (audioCtx.state !== "running") audioCtx.resume();
  return audioCtx;
};

class Recorder {
  constructor(btn, onBlob, label) {
    this.btn = btn; this.onBlob = onBlob; this.label = label; this.rec = null;
    btn.addEventListener("pointerdown", e => { e.preventDefault(); this.rec ? this.stop() : this.start(); });
    btn.addEventListener("pointerup", () => { if (this.rec && performance.now() - this.t0 > 600) this.stop(); });
  }
  async start() {
    stopAudio();
    const ctx = sharedCtx();
    let stream;
    try { stream = await navigator.mediaDevices.getUserMedia({audio: {echoCancellation: true, noiseSuppression: true}}); }
    catch (e) { return setStatus("Microphone unavailable: " + e.message + " (use http://localhost or https)", true); }
    this.t0 = performance.now(); this.chunks = [];
    this.rec = new MediaRecorder(stream);
    this.rec.ondataavailable = ev => this.chunks.push(ev.data);
    this.rec.onstop = () => {
      clearInterval(this.timer); this.nodes?.forEach(n => n.disconnect());
      stream.getTracks().forEach(t => t.stop());
      const blob = new Blob(this.chunks, {type: this.rec.mimeType}); this.rec = null;
      if (blob.size > 1000) this.onBlob(blob);
    };
    this.rec.start(); this.btn.classList.add("rec"); this.btn.textContent = "Listening… (tap to stop)";
    setStatus("Listening… speak now. It stops when you pause.");
    this.vad(ctx, stream);
  }
  // Auto-stop ~1.3 s after speech ends; give up after 10 s with no speech or 30 s total.
  vad(ctx, stream) {
    const src = ctx.createMediaStreamSource(stream), an = ctx.createAnalyser(), mute = ctx.createGain();
    an.fftSize = 1024; mute.gain.value = 0;
    src.connect(an); an.connect(mute); mute.connect(ctx.destination);  // keep the graph pulled
    this.nodes = [src, an, mute];
    const data = new Float32Array(an.fftSize);
    let heard = false, quietSince = performance.now(), floor = null;
    this.timer = setInterval(() => {  // setInterval keeps running when the tab is in the background
      if (!this.rec) return clearInterval(this.timer);
      an.getFloatTimeDomainData(data);
      const rms = Math.sqrt(data.reduce((s, v) => s + v * v, 0) / data.length), now = performance.now();
      // Adaptive threshold: track the background noise floor so quiet microphones still trigger.
      if (rms > 0) floor = floor === null || rms < floor ? rms : floor * 1.002;
      const threshold = Math.min(0.02, Math.max(0.004, (floor ?? 0.007) * 3));
      if (rms > threshold) { heard = true; quietSince = now; }
      const elapsed = now - this.t0;
      if ((heard && now - quietSince > 1300) || (!heard && elapsed > 10000) || elapsed > 30000) this.stop();
    }, 50);
  }
  stop() {
    if (this.rec?.state === "recording") this.rec.stop();
    this.btn.classList.remove("rec"); this.btn.textContent = this.label;
  }
}

new Recorder($("mic"), async blob => {
  setStatus("Transcribing…");
  const fd = new FormData();
  fd.append("audio", blob, "voice.webm"); fd.append("session", session);
  fd.append("lang_code", $("lang").value); fd.append("slow", $("slow").checked);
  await streamTurn("/api/stream/voice", {method: "POST", body: fd}, ev => {
    const unclear = ev.unclear_words.length ? `<div class="meta">Unclear: ${esc(ev.unclear_words.join(", "))}</div>` : "";
    add("user", `<i>(voice · ${esc(ev.lang_name)})</i> ${esc(ev.text)}${unclear}`);
  });
}, "Talk");

// ---------------------------------------------------------------- practice
let mineUrl = null, annotateTimer = null;
async function annotateTarget() {
  const text = $("target").value.trim();
  if (!text) { $("targetPh").innerHTML = ""; return; }
  const r = await fetch("/api/annotate", {method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({text, lang: $("lang").value || null})});
  if (r.ok) $("targetPh").innerHTML = phHtml(await r.json());
}
$("target").oninput = () => { clearTimeout(annotateTimer); annotateTimer = setTimeout(annotateTarget, 500); };
$("hear").onclick = () => { const t = $("target").value.trim(); if (t) speak(t, $("lang").value || null, false); };
$("hearSlow").onclick = () => { const t = $("target").value.trim(); if (t) speak(t, $("lang").value || null, true); };
$("playMine").onclick = () => { if (mineUrl) { stopAudio(); enqueue(mineUrl); } };

function diffHtml(diff) {
  if (!diff.length) return "";
  const t = diff.map(d => d.op === "equal" ? esc(d.target) : d.target ? `<span class="x">${esc(d.target)}</span>` : "").join("");
  const h = diff.map(d => d.op === "equal" ? esc(d.heard) : d.heard ? `<span class="ins">${esc(d.heard)}</span>` : "").join("");
  return `<div class="diff">expected /${t}/</div><div class="diff">you said /${h || "—"}/</div>`;
}

new Recorder($("pmic"), async blob => {
  const target = $("target").value.trim();
  if (!target) { $("presult").textContent = "Type a phrase first."; return; }
  if (mineUrl) URL.revokeObjectURL(mineUrl);
  mineUrl = URL.createObjectURL(blob); $("playMine").classList.remove("hidden");
  $("presult").textContent = "Scoring…";
  const fd = new FormData(); fd.append("audio", blob, "practice.webm");
  fd.append("target", target); fd.append("lang_code", $("lang").value);
  const r = await fetch("/api/practice", {method: "POST", body: fd});
  if (!r.ok) { $("presult").innerHTML = `<span class="err">${esc(await r.text())}</span>`; return; }
  const d = await r.json();
  const color = d.overall >= 85 ? "var(--ok)" : d.overall >= 65 ? "var(--read)" : "var(--bad)";
  $("presult").innerHTML = `
    <div class="score" style="color:${color}">${d.overall}/100</div>
    <div class="meta">Heard: “${esc(d.heard)}”</div>
    <div>${d.words.map((w, i) => `<span class="w ${w.ok ? "ok" : "bad"}" data-i="${i}" title="/${esc(w.ipa)}/">${esc(w.word)} ${w.score}</span>`).join("")}</div>
    <div id="wordDetail" class="meta">Click a word for details.</div>
    ${d.tips.length ? `<ul class="tips">${d.tips.map(t => `<li>${esc(t)}</li>`).join("")}</ul>` : `<div class="meta">Great job!</div>`}`;
  for (const chip of $("presult").querySelectorAll(".w")) chip.onclick = () => {
    const w = d.words[chip.dataset.i];
    $("wordDetail").innerHTML = `<div><b>${esc(w.word)}</b> /${esc(w.ipa)}/ <button class="small sec">Hear</button></div>${diffHtml(w.diff)}`;
    $("wordDetail").querySelector("button").onclick = () => speak(w.word, d.lang, true);
  };
  loadProgress();
}, "Record");

// ---------------------------------------------------------------- progress
function showTab(name) {
  for (const b of document.querySelectorAll(".tabs button")) b.classList.toggle("on", b.dataset.tab === name);
  $("tab-practice").classList.toggle("hidden", name !== "practice");
  $("tab-progress").classList.toggle("hidden", name !== "progress");
  if (name === "progress") loadProgress();
}
for (const b of document.querySelectorAll(".tabs button")) b.onclick = () => showTab(b.dataset.tab);

async function loadProgress() {
  const p = await (await fetch("/api/progress")).json();
  const pts = p.recent.map(r => r.overall);
  const spark = pts.length > 1 ? `<svg id="spark" viewBox="0 0 ${pts.length - 1} 100" preserveAspectRatio="none">
      <polyline fill="none" stroke="#4f8cff" stroke-width="3" vector-effect="non-scaling-stroke"
      points="${pts.map((v, i) => `${i},${100 - v}`).join(" ")}"/></svg>` : "";
  $("progress").innerHTML = `
    <div class="score">${p.average}<span class="meta" style="display:inline"> avg over ${p.attempts} attempts</span></div>
    ${spark}
    <h2 style="margin-top:12px">Words to review</h2>
    ${p.weak_words.length ? p.weak_words.map(w => `<div class="weak" data-w="${esc(w.word)}" data-l="${esc(w.lang)}">
      <span>${esc(w.word)} <span class="meta" style="display:inline">${esc(w.lang)}</span></span><span>${w.avg} · ${w.n}×</span></div>`).join("")
      : `<div class="meta">No weak words yet — record some practice.</div>`}`;
  for (const el of $("progress").querySelectorAll(".weak")) el.onclick = () => {
    $("target").value = el.dataset.w; $("lang").value = el.dataset.l; showTab("practice"); annotateTarget();
  };
}

// ---------------------------------------------------------------- boot
$("reset").onclick = async () => {
  await fetch("/api/reset?session=" + session, {method: "POST"});
  localStorage.session = crypto.randomUUID(); location.reload();
};

(async () => {
  try {
    const h = await (await fetch("/api/health")).json();
    for (const [code, [name]] of Object.entries(h.languages)) {
      const o = document.createElement("option");
      o.value = code; o.textContent = name + (h.neural_voices.includes(code) ? " ★" : "");
      $("lang").appendChild(o);
    }
    setStatus(h.llm_ready ? `Ready · ${h.llm} · whisper-${h.whisper} · ★ neural voice`
      : `LLM "${h.llm}" not available — start Ollama and pull the model.`, !h.llm_ready);
    for (const m of await (await fetch("/api/history?session=" + session)).json()) {
      if (m.role === "user") add("user", (m.mode === "voice" ? `<i>(voice · ${esc(m.lang_name)})</i> ` : "") + esc(m.content));
      else {
        const b = botBubble();
        for (const sn of m.sentences || [{text: m.content}]) b.sents.insertAdjacentHTML("beforeend", sentHtml(sn));
        finishBubble(b, m.content, m.lang, m.lang_name);
      }
    }
  } catch (e) { setStatus("Server unreachable: " + e.message, true); }
})();

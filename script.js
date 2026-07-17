// ── DOM refs ────────────────────────────────────────────────────────────────
const speakBtn    = document.getElementById("speakBtn");
const downloadBtn = document.getElementById("downloadBtn");
const textEl      = document.getElementById("text");
const langSel     = document.getElementById("languageSelect");
const voiceSel    = document.getElementById("voiceSelect");
const speedSlider = document.getElementById("speedSlider");
const statusEl    = document.getElementById("status");
const player      = document.getElementById("player");
const recordBtn   = document.getElementById("recordBtn");
const stopRecBtn  = document.getElementById("stopRecBtn");

let lastAudioUrl = null;

// ── Status helper ────────────────────────────────────────────────────────────
function setStatus(msg, type = "") {
  statusEl.textContent = msg;
  statusEl.className   = type;
}

// ── Load voices for selected language ───────────────────────────────────────
async function loadVoices(lang) {
  voiceSel.innerHTML = '<option value="">Loading…</option>';
  try {
    const res    = await fetch(`/voices?lang=${encodeURIComponent(lang)}`);
    const data   = await res.json();
    const voices = data.voices || [];

    voiceSel.innerHTML = "";
    if (!voices.length) {
      voiceSel.innerHTML = '<option value="">— no voices —</option>';
      return;
    }
    voices.forEach(v => {
      const opt = document.createElement("option");
      opt.value       = v.id;
      opt.textContent = v.name;
      voiceSel.appendChild(opt);
    });
  } catch (e) {
    voiceSel.innerHTML = '<option value="">Error loading</option>';
  }
}

// ── Language change handler ──────────────────────────────────────────────────
function onLangChange() {
  const lang = langSel.value;
  loadVoices(lang);
  if (recognition) {
    const sttLang = lang === "hi" ? "hi-IN"
                  : lang.startsWith("en") ? (lang === "en-gb" ? "en-GB" : "en-US")
                  : lang === "es" ? "es-ES"
                  : lang === "fr" ? "fr-FR"
                  : lang === "ja" ? "ja-JP"
                  : lang === "ko" ? "ko-KR"
                  : lang === "zh-cn" ? "zh-CN"
                  : "en-US";
    recognition.lang = sttLang;
  }
}

// Load default language voices on startup
loadVoices(langSel.value);

// ── Generate speech ──────────────────────────────────────────────────────────
async function speak() {
  const text     = textEl.value.trim();
  const language = langSel.value;
  const voice    = voiceSel.value;
  const speed    = parseFloat(speedSlider.value);

  if (!text) { setStatus("Pehle kuch text likhein!", "error"); return; }

  speakBtn.innerHTML   = '<span class="spinner"></span> Generating…';
  speakBtn.disabled    = true;
  downloadBtn.disabled = true;
  setStatus("", "");

  try {
    const res  = await fetch("/speak", {
      method : "POST",
      headers: { "Content-Type": "application/json" },
      body   : JSON.stringify({ text, language, voice, speed }),
    });
    const data = await res.json();

    if (!res.ok) {
      setStatus("❌ " + (data.error || res.statusText), "error");
      return;
    }

    lastAudioUrl         = data.audio_url;
    player.src           = lastAudioUrl;
    player.play().catch(() => {});
    downloadBtn.disabled = false;
    setStatus("✅ Speech ready — sun lo!", "success");

  } catch (e) {
    setStatus("Network error: " + e.message, "error");
  } finally {
    speakBtn.innerHTML = "▶ Generate Speech";
    speakBtn.disabled  = false;
  }
}

// ── Download ─────────────────────────────────────────────────────────────────
function downloadAudio() {
  if (!lastAudioUrl) return;
  const a    = document.createElement("a");
  a.href     = lastAudioUrl;
  a.download = "kokoro_speech.wav";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

// ── Speech-to-Text (Web Speech API) ─────────────────────────────────────────
let recognition = null;

if (!("webkitSpeechRecognition" in window) && !("SpeechRecognition" in window)) {
  recordBtn.disabled  = true;
  stopRecBtn.disabled = true;
} else {
  const SR    = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SR();
  recognition.lang            = "en-US";
  recognition.interimResults  = true;
  recognition.maxAlternatives = 1;

  recognition.onstart  = () => { setStatus("🎤 Bol do…", "info"); recordBtn.disabled = true; stopRecBtn.disabled = false; };
  recognition.onerror  = e  => { setStatus("Error: " + e.error, "error"); recordBtn.disabled = false; stopRecBtn.disabled = true; };
  recognition.onend    = ()  => { setStatus("Recording ruk gayi.", ""); recordBtn.disabled = false; stopRecBtn.disabled = true; };
  recognition.onresult = event => {
    let final = "", interim = "";
    for (let i = 0; i < event.results.length; i++) {
      const r = event.results[i];
      if (r.isFinal) final   += r[0].transcript;
      else           interim += r[0].transcript;
    }
    textEl.value = (textEl.value ? textEl.value + " " : "") + final + interim;
  };
}

recordBtn.addEventListener("click",  () => { if (recognition) { textEl.value = ""; recognition.start(); } });
stopRecBtn.addEventListener("click", () => { if (recognition) recognition.stop(); });
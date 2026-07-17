from flask import Flask, request, jsonify, render_template, url_for
from kokoro import KPipeline
import soundfile as sf
import numpy as np
import uuid
import os
import base64
from flask_cors import CORS

app = Flask(__name__, template_folder='templates')
CORS(app)

AUDIO_DIR = os.path.join(app.static_folder, "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

# ── Kokoro language code mapping ───────────────────────────────────────────
# Kokoro uses single-char lang codes internally
LANG_CODE_MAP = {
    "en":    "a",   # American English
    "en-gb": "b",   # British English
    "hi":    "h",   # Hindi
    "es":    "e",   # Spanish
    "fr":    "f",   # French
    "it":    "i",   # Italian
    "pt":    "p",   # Brazilian Portuguese
    "zh-cn": "z",   # Chinese (Mandarin)
    "ja":    "j",   # Japanese
    "ko":    "k",   # Korean
}

# ── Available voices per Kokoro lang_code ──────────────────────────────────
VOICES_MAP = {
    "a": [
        {"id": "af_heart",   "name": "Heart (F)"},
        {"id": "af_bella",   "name": "Bella (F)"},
        {"id": "af_nicole",  "name": "Nicole (F)"},
        {"id": "af_sarah",   "name": "Sarah (F)"},
        {"id": "am_adam",    "name": "Adam (M)"},
        {"id": "am_michael", "name": "Michael (M)"},
        {"id": "am_liam",    "name": "Liam (M)"},
    ],
    "b": [
        {"id": "bf_emma",     "name": "Emma (F)"},
        {"id": "bf_isabella", "name": "Isabella (F)"},
        {"id": "bm_george",   "name": "George (M)"},
        {"id": "bm_lewis",    "name": "Lewis (M)"},
    ],
    "h": [
        {"id": "hf_alpha", "name": "Alpha (F)"},
        {"id": "hf_beta",  "name": "Beta (F)"},
        {"id": "hm_omega", "name": "Omega (M)"},
        {"id": "hm_psi",   "name": "Psi (M)"},
    ],
    "e": [
        {"id": "ef_dora",  "name": "Dora (F)"},
        {"id": "em_alex",  "name": "Alex (M)"},
    ],
    "f": [
        {"id": "ff_siwis", "name": "Siwis (F)"},
    ],
    "i": [
        {"id": "if_sara",   "name": "Sara (F)"},
        {"id": "im_nicola", "name": "Nicola (M)"},
    ],
    "p": [
        {"id": "pf_dora", "name": "Dora (F)"},
        {"id": "pm_alex", "name": "Alex (M)"},
    ],
    "z": [
        {"id": "zf_xiaobei",  "name": "Xiaobei (F)"},
        {"id": "zf_xiaoxiao", "name": "Xiaoxiao (F)"},
        {"id": "zm_yunxi",    "name": "Yunxi (M)"},
        {"id": "zm_yunyang",  "name": "Yunyang (M)"},
    ],
    "j": [
        {"id": "jf_alpha",     "name": "Alpha (F)"},
        {"id": "jf_gongitsune","name": "Gongitsune (F)"},
        {"id": "jm_kumo",      "name": "Kumo (M)"},
    ],
    "k": [
        {"id": "kf_alpha",  "name": "Alpha (F)"},
        {"id": "km_hyunsu", "name": "Hyunsu (M)"},
    ],
}

# ── Supported languages exposed to frontend ────────────────────────────────
SUPPORTED_LANGUAGES = [
    {"name": "🇮🇳 Hindi",           "code": "hi"},
    {"name": "🇺🇸 English (US)",    "code": "en"},
    {"name": "🇬🇧 English (UK)",    "code": "en-gb"},
    {"name": "🇪🇸 Spanish",         "code": "es"},
    {"name": "🇫🇷 French",          "code": "fr"},
    {"name": "🇩🇪 Italian",         "code": "it"},
    {"name": "🇧🇷 Portuguese (BR)", "code": "pt"},
    {"name": "🇨🇳 Chinese",         "code": "zh-cn"},
    {"name": "🇯🇵 Japanese",        "code": "ja"},
    {"name": "🇰🇷 Korean",          "code": "ko"},
]

# ── Lazy-loaded pipeline cache ─────────────────────────────────────────────
_pipelines: dict[str, KPipeline] = {}

def get_pipeline(lang_code: str) -> KPipeline:
    """Return a cached KPipeline for the given Kokoro lang_code."""
    if lang_code not in _pipelines:
        print(f"Loading Kokoro pipeline for lang_code='{lang_code}'...")
        _pipelines[lang_code] = KPipeline(lang_code=lang_code)
        print(f"  Pipeline '{lang_code}' ready ✓")
    return _pipelines[lang_code]

# ── Helper: generate audio numpy array ────────────────────────────────────
def synthesize(text: str, lang_code: str, voice: str, speed: float = 1.0) -> np.ndarray:
    pipeline = get_pipeline(lang_code)
    chunks = []
    for _, _, audio in pipeline(text, voice=voice, speed=speed):
        if audio is not None:
            chunks.append(audio)
    if not chunks:
        raise RuntimeError("Kokoro returned no audio for the given input.")
    return np.concatenate(chunks, axis=0)

# ── Routes ─────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    voices_json = {k: VOICES_MAP.get(k, []) for k in LANG_CODE_MAP.values()}
    return render_template(
        "index.html",
        languages=SUPPORTED_LANGUAGES,
        voices_map=VOICES_MAP,
        lang_code_map=LANG_CODE_MAP,
    )

@app.route("/languages", methods=["GET"])
def get_languages():
    return jsonify(SUPPORTED_LANGUAGES)

@app.route("/voices", methods=["GET"])
def get_voices():
    """Return voices for a given language code. ?lang=hi"""
    lang = request.args.get("lang", "en")
    k_code = LANG_CODE_MAP.get(lang, "a")
    voices = VOICES_MAP.get(k_code, [])
    return jsonify({"lang_code": k_code, "voices": voices})

@app.route("/speak", methods=["POST"])
def speak():
    data     = request.get_json(force=True)
    text     = data.get("text", "").strip()
    language = data.get("language", "en")
    voice    = data.get("voice", "")
    speed    = float(data.get("speed", 1.0))

    if not text:
        return jsonify({"error": "Text is empty"}), 400

    k_code = LANG_CODE_MAP.get(language, "a")

    # Default voice fallback
    if not voice:
        default_voices = VOICES_MAP.get(k_code, [])
        voice = default_voices[0]["id"] if default_voices else "af_heart"

    filename = f"{uuid.uuid4().hex}.wav"
    filepath = os.path.join(AUDIO_DIR, filename)

    try:
        audio = synthesize(text, k_code, voice, speed)
        sf.write(filepath, audio, 24000)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    audio_url = url_for("static", filename=f"audio/{filename}", _external=True)
    return jsonify({"audio_url": audio_url})

@app.route("/api/tts", methods=["POST"])
def tts_api():
    data     = request.get_json(force=True)
    text     = data.get("text", "").strip()
    language = data.get("language", "en")
    voice    = data.get("voice", "")
    speed    = float(data.get("speed", 1.0))

    if not text:
        return jsonify({"success": False, "error": "Text is required"}), 400

    k_code = LANG_CODE_MAP.get(language, "a")
    if not voice:
        default_voices = VOICES_MAP.get(k_code, [])
        voice = default_voices[0]["id"] if default_voices else "af_heart"

    filename = f"{uuid.uuid4().hex}.wav"
    filepath = os.path.join(AUDIO_DIR, filename)

    try:
        audio = synthesize(text, k_code, voice, speed)
        sf.write(filepath, audio, 24000)
        with open(filepath, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode("utf-8")
        return jsonify({"success": True, "audio_base64": audio_b64})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=False)
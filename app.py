import os, uuid, base64, json, requests
from flask import Flask, request, abort, render_template, url_for

# ── Config ───────────────────────────────────────────
BASE_DIR      = os.path.abspath(os.path.dirname(__file__))
UPLOAD_DIR    = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

GPT_ENDPOINT  = "https://text.pollinations.ai/openai"
KONTEXT_FMT   = (
    "https://image.pollinations.ai/prompt/{prompt}"
    "?model=kontext&image={img}"
)

# ── App ──────────────────────────────────────────────
app = Flask(
    __name__,
    static_url_path="/uploads",       # → http://host/uploads/<file>
    static_folder=UPLOAD_DIR,
    template_folder="templates"
)

# ── Helpers ──────────────────────────────────────────
def save_upload(f):
    ext   = (f.filename.rsplit(".", 1)[-1] or "jpg").lower()
    fname = f"{uuid.uuid4().hex}.{ext}"
    path  = os.path.join(UPLOAD_DIR, fname)
    f.save(path)
    pub   = url_for("static", filename=fname, _external=True)
    return path, pub

def gpt_payload(data_uri, inspiration):
    return {
        "model": "openai",
        "messages": [
            { "role": "system",
              "content": (
                  "You are a meme master. "
                  "Return JSON with keys: caption, kontext_prompt. "
                  "kontext_prompt must embed the caption (in quotes) so it shows on the image."
              )},
            { "role": "user",
              "content": [
                 { "type": "text", "text": f'Inspiration: "{inspiration or "none"}"' },
                 { "type": "image_url", "image_url": { "url": data_uri } }
              ]}
        ],
        "seed": 42
    }

def call_gpt(payload):
    r = requests.post(GPT_ENDPOINT, json=payload, timeout=120)
    r.raise_for_status()
    raw = r.json()["choices"][0]["message"]["content"]
    return json.loads(raw)           # {'caption': ..., 'kontext_prompt': ...}

def call_kontext(prompt, img_url):
    full = KONTEXT_FMT.format(
        prompt = requests.utils.quote(prompt, safe=""),
        img    = requests.utils.quote(img_url,   safe="")
    )
    r = request

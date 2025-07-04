# app.py
# Flask backend that:
# 1. saves the uploaded image
# 2. sends a base‑64 data‑URI to Pollinations GPT (vision)
# 3. receives a JSON {caption, kontext_prompt}
# 4. calls Flux/Kontext with the hosted image URL + prompt
# 5. returns the edited meme bytes

import os, uuid, base64, json, requests
from flask import Flask, request, abort, send_from_directory, render_template, url_for

# ── Config ──────────────────────────────────────────────
BASE_DIR    = os.path.dirname(__file__)
UPLOAD_DIR  = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

GPT_ENDPOINT    = "https://text.pollinations.ai/openai"
KONTEXT_PATTERN = (
    "https://image.pollinations.ai/prompt/{prompt}"
    "?model=kontext&image={img}"
)

# ── Flask app ───────────────────────────────────────────
app = Flask(
    __name__,
    static_url_path="/uploads",          # serve /uploads/<file>
    static_folder=UPLOAD_DIR,
    template_folder="templates"
)

# ── Helper functions ───────────────────────────────────
def save_upload(file):
    ext   = (file.filename.rsplit(".", 1)[-1] or "jpg").lower()
    fname = f"{uuid.uuid4().hex}.{ext}"
    path  = os.path.join(UPLOAD_DIR, fname)
    file.save(path)
    # Public URL: https://<your‑render‑url>/uploads/<fname>
    url   = url_for("static", filename=fname, _external=True)
    return path, url

def build_gpt_payload(data_uri, inspiration):
    return {
        "model": "openai",
        "seed": 42,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a world‑class meme artist. "
                    "Return *only* valid JSON with keys:\n"
                    "  caption        – meme text\n"
                    "  kontext_prompt – detailed prompt for the Kontext model "
                    "that *embeds* the caption in quotes so it appears on the image."
                )
            },
            {
                "role": "user",
                "content": [
                    {"type": "text",
                     "text": f'Inspiration: "{inspiration or "none"}"'},
                    {"type": "image_url",
                     "image_url": {"url": data_uri}}
                ]
            }
        ]
    }

def call_gpt(payload):
    r = requests.post(GPT_ENDPOINT, json=payload, timeout=120)
    r.raise_for_status()
    return json.loads(r.json()["choices"][0]["message"]["content"])

def call_kontext(prompt, img_url):
    url = KONTEXT_PATTERN.format(
        prompt = requests.utils.quote(prompt, safe=""),
        img    = requests.utils.quote(img_url, safe="")
    )
    r = requests.get(url, timeout=300)
    r.raise_for_status()
    return r.content

# ── Routes ──────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.post("/generate")
def generate():
    if "image" not in request.files:
        abort(400, "No file uploaded")
    file         = request.files["image"]
    inspiration  = request.form.get("inspiration", "")

    # 1. Save + host the original image
    img_path, img_url = save_upload(file)

    # 2. Build data‑URI for GPT
    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    mime = "jpeg" if file.mimetype == "image/jpeg" else file.mimetype.split("/")[-1]
    data_uri = f"data:image/{mime};base64,{b64}"

    # 3. GPT: caption & kontext prompt
    gpt_json   = call_gpt(build_gpt_payload(data_uri, inspiration))
    k_prompt   = gpt_json["kontext_prompt"]

    # 4. Kontext: edited meme
    meme_bytes = call_kontext(k_prompt, img_url)

    # 5. Send meme to browser
    return (meme_bytes, 200, {"Content-Type": "image/jpeg"})

# ── Entrypoint for local dev ────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)

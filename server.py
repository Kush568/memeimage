# app.py
# ──────
# Requirements: pip install flask requests python-dotenv
import os, uuid, base64, json, requests
from flask import Flask, request, jsonify, send_file, abort, url_for

# ── Config ─────────────────────────────────────────────────────────
UPLOAD_DIR      = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

GPT_ENDPOINT    = "https://text.pollinations.ai/openai"
KONTEXT_PATTERN = "https://image.pollinations.ai/prompt/{prompt}?model=kontext&image={img}"

app = Flask(__name__, static_url_path="/uploads", static_folder=UPLOAD_DIR)  # serve uploads

# ── Helpers ─────────────────────────────────────────────────────────
def save_upload(file_storage):
    """Save user image and return local path + public URL."""
    ext = (file_storage.filename.rsplit(".", 1)[-1] or "jpg").lower()
    fname = f"{uuid.uuid4().hex}.{ext}"
    path  = os.path.join(UPLOAD_DIR, fname)
    file_storage.save(path)
    # url_for builds something like /uploads/<fname>
    return path, url_for("static", filename=fname, _external=True)

def build_gpt_payload(data_uri, inspiration):
    return {
        "model": "openai",           # pollinations • vision capable
        "seed": 42,
        "messages": [
            { "role": "system",
              "content": (
                "You are a world‑class meme artist. "
                "Respond ONLY with JSON containing keys:\n"
                "  caption        – the meme text\n"
                "  kontext_prompt – a detailed instruction for the Kontext model "
                "(must embed the caption in quotes so it appears on the image)."
              )
            },
            { "role": "user",
              "content": [
                  { "type": "text",
                    "text": f'Inspiration: "{inspiration or "none"}"' },
                  { "type": "image_url",
                    "image_url": { "url": data_uri } }
              ]
            }
        ]
    }

def call_gpt(payload):
    r = requests.post(GPT_ENDPOINT, json=payload, timeout=120)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    return json.loads(content)      # must be valid JSON

def call_kontext(prompt, img_url):
    full = KONTEXT_PATTERN.format(
        prompt   = requests.utils.quote(prompt, safe=""),
        img      = requests.utils.quote(img_url,  safe="")
    )
    r = requests.get(full, timeout=300)   # up to 5 min
    r.raise_for_status()
    return r.content                      # raw image bytes

# ── Routes ──────────────────────────────────────────────────────────
@app.post("/generate")
def generate():
    if "image" not in request.files:
        abort(400, "missing file")
    img_file       = request.files["image"]
    inspiration    = request.form.get("inspiration", "")

    # 1. Save user image -> public URL
    img_path, img_url = save_upload(img_file)

    # 2. Build base‑64 data‑URI for GPT
    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    mime = "jpeg" if img_file.mimetype == "image/jpeg" else img_file.mimetype.split("/")[-1]
    data_uri = f"data:image/{mime};base64,{b64}"

    # 3. GPT: caption + kontext prompt
    gpt_json   = call_gpt(build_gpt_payload(data_uri, inspiration))
    k_prompt   = gpt_json["kontext_prompt"]

    # 4. Kontext: edited meme
    meme_bytes = call_kontext(k_prompt, img_url)

    # 5. Return the meme image bytes
    return (meme_bytes, 200, {"Content-Type": "image/jpeg"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)

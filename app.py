# app.py
import streamlit as st
import requests
import base64

# ✅ Page setup
st.set_page_config(page_title="Image Generator", layout="centered")
st.title("🖼️ Image Generator (Stability AI)")

# ✅ Hardcoded Stability API Key
STABILITY_API_KEY = "sk-ccceUzPNm0Q4StkwZIu8dvWyXc84N2sw5olVBMG7PPfCtpgP"
DEFAULT_MODEL = "stable-diffusion-xl-1024-v1-0"
BASE_URL_TEMPLATE = "https://api.stability.ai/v1/generation/{model}/text-to-image"

# ✅ Prompt input
prompt = st.text_area(
    "Enter your prompt",
    value="A professional portrait of a cyborg samurai, cinematic lighting, ultra-detailed"
)

# ✅ Fixed generation settings
GEN_SETTINGS = {
    "width": 1024,
    "height": 1024,
    "steps": 49,
    "samples": 1,
    "cfg_scale": 9,
}

def generate_image(prompt: str):
    """Send request to Stability API and return images."""
    url = BASE_URL_TEMPLATE.format(model=DEFAULT_MODEL)
    headers = {
        "Authorization": f"Bearer {STABILITY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "text_prompts": [{"text": prompt}],
        "cfg_scale": GEN_SETTINGS["cfg_scale"],
        "height": GEN_SETTINGS["height"],
        "width": GEN_SETTINGS["width"],
        "sampler": "DDIM",
        "steps": GEN_SETTINGS["steps"],
        "samples": GEN_SETTINGS["samples"],
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=120)

    if resp.status_code != 200:
        try:
            err = resp.json()
        except Exception:
            err = resp.text
        st.error(f"Stability API error ({resp.status_code}): {err}")
        return []

    try:
        data = resp.json()
    except Exception as e:
        st.error(f"Invalid JSON from Stability: {e}")
        return []

    artifacts = []
    if isinstance(data, dict) and "artifacts" in data:
        for art in data["artifacts"]:
            b64 = art.get("base64") or art.get("b64") or art.get("data")
            mime = art.get("mime", "image/png")
            if not b64:
                continue
            if isinstance(b64, str) and b64.startswith("data:"):
                b64 = b64.split(",", 1)[1]
            artifacts.append({"b64": b64, "mime": mime})
    return artifacts

# ✅ Generate button
if st.button("Generate"):
    if not prompt.strip():
        st.error("Please provide a prompt.")
    else:
        with st.spinner("Generating image..."):
            images = generate_image(prompt)

        if not images:
            st.error("No images returned.")
        else:
            st.success(f"Received {len(images)} image(s) from model {DEFAULT_MODEL}")
            for idx, art in enumerate(images):
                b64 = art.get("b64")
                mime = art.get("mime", "image/png")
                if not b64:
                    continue
                try:
                    img_bytes = base64.b64decode(b64)
                except Exception as e:
                    st.error(f"Failed to decode image {idx}: {e}")
                    continue

                st.image(img_bytes, caption=f"Image {idx+1}", use_column_width=True)
                st.download_button(
                    label=f"Download image {idx+1}",
                    data=img_bytes,
                    file_name=f"gen_image_{idx+1}.png",
                    mime=mime,
                )


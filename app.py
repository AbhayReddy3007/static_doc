# app.py (Streamlit + Vertex AI, with proper secrets handling for Streamlit Cloud)
import os
import datetime
import json
import streamlit as st

import vertexai
from vertexai.preview.vision_models import ImageGenerationModel

# ---------------- CONFIG ----------------
PROJECT_ID = "drl-zenai-prod"
REGION = "us-central1"

# Load Google Cloud credentials from Streamlit secrets
creds_path = "/tmp/service_account.json"
service_account_info = json.loads(st.secrets["gcp_service_account"])
with open(creds_path, "w") as f:
    json.dump(service_account_info, f)

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path

# Init Vertex AI
vertexai.init(project=PROJECT_ID, location=REGION)

IMAGE_MODEL_NAME = "imagen-4.0-generate-001"
IMAGE_MODEL = ImageGenerationModel.from_pretrained(IMAGE_MODEL_NAME)

# ---------------- STREAMLIT UI ----------------
st.set_page_config(page_title="AI Image Generator", layout="wide")
st.title("🖼️ AI Image Generator")

# ---------------- STATE ----------------
if "generated_images" not in st.session_state:
    st.session_state.generated_images = []

# ---------------- UI ----------------
prompt = st.text_area("✨ Enter your prompt to generate an image:", height=120)

if st.button("🚀 Generate Image"):
    if not prompt.strip():
        st.warning("Please enter a prompt!")
    else:
        with st.spinner("Generating image..."):
            try:
                resp = IMAGE_MODEL.generate_images(prompt=prompt, number_of_images=1)

                if resp.images and hasattr(resp.images[0], "_image_bytes"):
                    img_bytes = resp.images[0]._image_bytes
                else:
                    st.error("❌ No image data returned from Imagen 4")
                    st.stop()

                # Save file locally (optional on Streamlit Cloud)
                output_dir = os.path.join(os.path.dirname(__file__), "generated_images")
                os.makedirs(output_dir, exist_ok=True)
                filename = f"image_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                filepath = os.path.join(output_dir, filename)

                with open(filepath, "wb") as f:
                    f.write(img_bytes)

                # Show image
                st.image(img_bytes, caption=filename, use_container_width=True)

                # Download button
                st.download_button(
                    "⬇️ Download Image",
                    data=img_bytes,
                    file_name=filename,
                    mime="image/png"
                )

                # Store in session history
                st.session_state.generated_images.append({"filename": filename, "content": img_bytes})

            except Exception as e:
                st.error(f"⚠️ Image generation error: {e}")

# ---------------- HISTORY ----------------
if st.session_state.generated_images:
    st.subheader("📂 Past Generated Images")
    for i, img in enumerate(st.session_state.generated_images):
        with st.expander(f"Image {i+1}: {img['filename']}"):
            st.image(img["content"], caption=img["filename"], use_container_width=True)
            st.download_button(
                "⬇️ Download Again",
                data=img["content"],
                file_name=img["filename"],
                mime="image/png",
                key=f"download_img_{i}")

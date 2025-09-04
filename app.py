# app.py
import io
import requests
import streamlit as st

BACKEND_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Document Summarizer (Mistral)", layout="centered")

st.title("📄 Document Summarizer (Mistral Small)")
st.write("Upload a PDF, DOCX, or TXT and get a comprehensive, exhaustive summary.")

uploaded_file = st.file_uploader("Upload a document", type=["pdf", "docx", "txt"])

if uploaded_file is not None:
    with st.spinner("Processing & summarizing with Mistral Small..."):
        files = {
            "file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type or "application/octet-stream")
        }
        res = requests.post(f"{BACKEND_URL}/upload/", files=files)

    if res.status_code == 200:
        data = res.json()
        st.success(f"✅ Processed **{data.get('filename','file')}** — "
                   f"{data.get('chars', 0)} characters across {data.get('chunks', 1)} chunk(s).")
        summary = data.get("summary", "")
        st.subheader("Comprehensive Summary")
        st.markdown(summary)

        # Download as Markdown
        md_bytes = io.BytesIO(summary.encode("utf-8"))
        base = (data.get("filename", "document").rsplit(".", 1)[0]) or "document"
        st.download_button(
            "⬇️ Download Summary (.md)",
            data=md_bytes,
            file_name=f"{base}_summary.md",
            mime="text/markdown"
        )
    else:
        try:
            err = res.json()
        except Exception:
            err = {"detail": res.text}
        st.error(f"❌ Failed: {err.get('detail', 'Unknown error')}")

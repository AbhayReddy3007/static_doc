import copy
import requests
import streamlit as st

BACKEND_URL = "http://127.0.0.1:8000"  # FastAPI backend

st.set_page_config(page_title="AI Productivity Suite", layout="wide")
st.title("Chatbot")

# ---------------- Helpers ----------------
def extract_filename_from_cd(resp):
    cd = resp.headers.get("content-disposition", "")
    if "filename=" in cd:
        return cd.split("filename=")[-1].strip().strip('"')
    return None

def render_outline_preview(outline_data, mode="ppt"):
    if not outline_data:
        st.info("No outline available.")
        return False

    title = outline_data.get("title", "Untitled")
    items = outline_data.get("slides", []) if mode == "ppt" else outline_data.get("sections", [])
    st.subheader(f"📝 Preview Outline: {title}")

    for idx, item in enumerate(items, start=1):
        item_title = item.get("title", f"{'Slide' if mode=='ppt' else 'Section'} {idx}")
        item_desc = item.get("description", "")
        with st.expander(f"{'Slide' if mode=='ppt' else 'Section'} {idx}: {item_title}", expanded=False):
            st.markdown(item_desc.replace("\n", "\n\n"))
    return len(items) > 0


# ---------------- STATE ----------------
defaults = {
    "messages": [],
    "outline_chat": None,
    "outline_mode": None,  # "ppt" or "doc"
    "generated_files": [],
    "summary_text": None,
    "summary_title": None,
    "doc_chat_history": [],
    "outline_from_summary": None,
    "generated_images": [],  # store past generated images
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ---------------- CHAT HISTORY ----------------
for role, content in st.session_state.messages:
    with st.chat_message(role):
        st.markdown(content)

# ---------------- Past Generated Files ----------------
for i, file_info in enumerate(st.session_state.generated_files):
    with st.chat_message("assistant"):
        if file_info["type"] == "ppt":
            st.markdown("✅ PPT generated earlier! Download below:")
            st.download_button(
                "⬇️ Download PPT",
                data=file_info["content"] if file_info["content"] else b"",
                file_name=file_info["filename"],
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                key=f"past_download_ppt_{i}"
            )
        elif file_info["type"] == "doc":
            st.markdown("✅ Document generated earlier! Download below:")
            st.download_button(
                "⬇️ Download Document",
                data=file_info["content"] if file_info["content"] else b"",
                file_name=file_info["filename"],
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"past_download_doc_{i}"
            )

# ---------------- Past Generated Images ----------------
for i, img_info in enumerate(st.session_state.generated_images):
    with st.chat_message("assistant"):
        st.markdown("🖼️ Image generated earlier:")
        st.image(img_info["content"], caption=img_info["filename"], use_container_width=True)
        st.download_button(
            "⬇️ Download Image",
            data=img_info["content"],
            file_name=img_info["filename"],
            mime="image/png",
            key=f"past_download_img_{i}"
        )


# ---------------- GENERAL CHAT ----------------
if prompt := st.chat_input("Type a message, ask for a PPT, DOC, or Image ..."):
    st.session_state.messages.append(("user", prompt))
    text = prompt.lower()

    try:
        if "ppt" in text or "presentation" in text or "slides" in text:
            with st.spinner("Generating PPT outline..."):
                resp = requests.post(f"{BACKEND_URL}/generate-ppt-outline", json={"description": prompt}, timeout=120)
                if resp.status_code == 200:
                    st.session_state.outline_chat = resp.json()
                    st.session_state.outline_mode = "ppt"
                    st.session_state.messages.append(("assistant", "✅ PPT outline generated! Preview below."))
                else:
                    st.session_state.messages.append(("assistant", f"❌ PPT outline failed: {resp.text}"))

        elif "doc" in text or "document" in text or "report" in text or "pages" in text or "sections" in text:
            with st.spinner("Generating DOC outline..."):
                resp = requests.post(f"{BACKEND_URL}/generate-doc-outline", json={"description": prompt}, timeout=120)
                if resp.status_code == 200:
                    st.session_state.outline_chat = resp.json()
                    st.session_state.outline_mode = "doc"
                    st.session_state.messages.append(("assistant", "✅ DOC outline generated! Preview below."))
                else:
                    st.session_state.messages.append(("assistant", f"❌ DOC outline failed: {resp.text}"))

        elif "image" in text or "picture" in text or "photo" in text:
            with st.spinner("Generating Image..."):
                resp = requests.post(f"{BACKEND_URL}/generate-image", json={"prompt": prompt}, timeout=180)
                if resp.status_code == 200:
                    img_bytes = resp.content
                    filename = extract_filename_from_cd(resp) or f"image_{len(st.session_state.generated_images)+1}.png"

                    # Store image
                    st.session_state.generated_images.append({
                        "filename": filename,
                        "content": img_bytes,
                    })

                    # Show image directly
                    st.image(img_bytes, caption=filename, use_container_width=True)

                    # Download button
                    st.download_button(
                        "⬇️ Download Image",
                        data=img_bytes,
                        file_name=filename,
                        mime="image/png",
                        key=f"download_img_{filename}"
                    )

                    st.session_state.messages.append(("assistant", "✅ Image generated!"))
                else:
                    st.session_state.messages.append(("assistant", f"❌ Image generation failed: {resp.text}"))

        else:
            resp = requests.post(f"{BACKEND_URL}/chat", json={"message": prompt}, timeout=60)
            bot_reply = resp.json().get("response", "⚠️ Error")
            st.session_state.messages.append(("assistant", bot_reply))

    except Exception as e:
        st.session_state.messages.append(("assistant", f"⚠️ Backend error: {e}"))

    st.rerun()

# ---------------- OUTLINE PREVIEW + ACTIONS ----------------
if st.session_state.outline_chat:
    mode = st.session_state.outline_mode
    outline = st.session_state.outline_chat

    render_outline_preview(outline, mode=mode)

    new_title = st.text_input("📌 Edit Title", value=outline.get("title", "Untitled"), key=f"title_{mode}")
    feedback_box = st.text_area("✏️ Feedback for outline (optional):", value="", key=f"feedback_chat_{mode}")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 Apply Feedback"):
            with st.spinner("Updating outline..."):
                try:
                    edit_payload = {"outline": outline, "feedback": feedback_box}
                    endpoint = f"{BACKEND_URL}/edit-ppt-outline" if mode == "ppt" else f"{BACKEND_URL}/edit-doc-outline"
                    resp = requests.post(endpoint, json=edit_payload, timeout=120)
                    if resp.status_code == 200:
                        updated_outline = resp.json()
                        updated_outline["title"] = new_title.strip() if new_title else updated_outline["title"]
                        st.session_state.outline_chat = updated_outline
                        st.success("✅ Outline updated!")
                        st.rerun()
                    else:
                        st.error(f"❌ Edit failed: {resp.status_code} — {resp.text}")
                except Exception as e:
                    st.error(f"❌ Edit error: {e}")

    with col2:
        if st.button(f"✅ Generate {mode.upper()}"):
            with st.spinner(f"Generating {mode.upper()}..."):
                try:
                    outline_to_send = copy.deepcopy(outline)
                    outline_to_send["title"] = new_title.strip() if new_title else outline_to_send["title"]

                    endpoint = f"{BACKEND_URL}/generate-ppt" if mode == "ppt" else f"{BACKEND_URL}/generate-doc"
                    resp = requests.post(endpoint, json={"outline": outline_to_send}, timeout=180)
                    if resp.status_code == 200:
                        filename = extract_filename_from_cd(resp) or (
                            "presentation.pptx" if mode == "ppt" else "document.docx"
                        )

                        st.success(f"✅ {mode.upper()} generated successfully!")
                        st.download_button(
                            f"⬇️ Download {mode.upper()}",
                            data=resp.content if resp.content else b"",
                            file_name=filename,
                            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                                 if mode == "ppt"
                                 else "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"download_{mode}_{filename}"
                        )

                        st.session_state.generated_files.append({
                            "type": mode,
                            "filename": filename,
                            "content": resp.content,
                        })

                        st.session_state.outline_chat = None
                    else:
                        st.error(f"❌ Generation failed: {resp.status_code} — {resp.text}")
                except Exception as e:
                    st.error(f"❌ Generation error: {e}")


# ---------------- DOC UPLOAD SECTION ----------------
uploaded_file = st.file_uploader("📂 Upload a document", type=["pdf", "docx", "txt", "md"])

if uploaded_file is not None:
    with st.spinner("Processing uploaded file..."):
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type or "application/octet-stream")}
        try:
            res = requests.post(f"{BACKEND_URL}/upload/", files=files, timeout=180)
        except Exception as e:
            st.error(f"❌ Summarizer backend error: {e}")
            res = None

    if res and res.status_code == 200:
        data = res.json()
        st.session_state.summary_text = data.get("summary", "")
        st.session_state.summary_title = data.get("title", "Summary")
        st.success(f"✅ Document uploaded! Suggested Title: **{st.session_state.summary_title}**. You can now chat with it.")


# ---------------- CHAT WITH DOCUMENT ----------------
if st.session_state.summary_text:
    st.markdown("💬 **Chat with your uploaded document**")

    for role, content in st.session_state.doc_chat_history:
        with st.chat_message(role):
            st.markdown(content)

    if doc_prompt := st.chat_input("Ask a question about the uploaded document..."):
        st.session_state.doc_chat_history.append(("user", doc_prompt))
        text = doc_prompt.lower()

        try:
            if "ppt" in text or "presentation" in text or "slides" in text:
                with st.spinner("Generating PPT outline from document..."):
                    resp = requests.post(
                        f"{BACKEND_URL}/generate-ppt-outline",
                        json={"description": st.session_state.summary_text + "\n\n" + doc_prompt},
                        timeout=180,
                    )
                    if resp.status_code == 200:
                        outline_data = resp.json()
                        outline_data["title"] = st.session_state.summary_title
                        st.session_state.outline_from_summary = outline_data
                        st.session_state.outline_mode = "ppt"
                        st.session_state.doc_chat_history.append(("assistant", "✅ Generated PPT outline from document. Preview below."))
                    else:
                        st.session_state.doc_chat_history.append(("assistant", f"❌ PPT outline failed: {resp.text}"))

            elif "doc" in text or "document" in text or "report" in text or "pages" in text or "sections" in text:
                with st.spinner("Generating DOC outline from document..."):
                    resp = requests.post(
                        f"{BACKEND_URL}/generate-doc-outline",
                        json={"description": st.session_state.summary_text + "\n\n" + doc_prompt},
                        timeout=180,
                    )
                    if resp.status_code == 200:
                        outline_data = resp.json()
                        outline_data["title"] = st.session_state.summary_title
                        st.session_state.outline_from_summary = outline_data
                        st.session_state.outline_mode = "doc"
                        st.session_state.doc_chat_history.append(("assistant", "✅ Generated DOC outline from document. Preview below."))
                    else:
                        st.session_state.doc_chat_history.append(("assistant", f"❌ DOC outline failed: {resp.text}"))

            else:
                resp = requests.post(
                    f"{BACKEND_URL}/chat-doc",
                    json={"message": doc_prompt, "document_text": st.session_state.summary_text},
                    timeout=120,
                )
                if resp.status_code == 200:
                    answer = resp.json().get("response", "⚠️ No answer")
                else:
                    answer = f"❌ Error: {resp.status_code} — {resp.text}"
                st.session_state.doc_chat_history.append(("assistant", answer))

        except Exception as e:
            st.session_state.doc_chat_history.append(("assistant", f"⚠️ Backend error: {e}"))

        st.rerun()


# ---------------- OUTLINE FROM UPLOAD ----------------
if st.session_state.outline_from_summary:
    mode = st.session_state.outline_mode
    outline_preview = st.session_state.outline_from_summary

    render_outline_preview(outline_preview, mode=mode)

    new_title_upload = st.text_input("📌 Edit Title (Upload Flow)", value=outline_preview.get("title", "Untitled"), key=f"title_upload_{mode}")
    feedback_box = st.text_area("✏️ Feedback for outline (optional):", value="", key=f"feedback_upload_{mode}")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 Apply Feedback (Upload Flow)"):
            with st.spinner("Applying feedback..."):
                edit_payload = {"outline": outline_preview, "feedback": feedback_box}
                endpoint = f"{BACKEND_URL}/edit-ppt-outline" if mode == "ppt" else f"{BACKEND_URL}/edit-doc-outline"
                edit_resp = requests.post(endpoint, json=edit_payload, timeout=120)
                if edit_resp.status_code == 200:
                    updated_outline = edit_resp.json()
                    updated_outline["title"] = new_title_upload.strip() if new_title_upload else updated_outline["title"]
                    st.session_state.outline_from_summary = updated_outline
                    st.success("✅ Outline updated")
                else:
                    st.error(f"❌ Edit failed: {edit_resp.status_code} — {edit_resp.text}")

    with col2:
        if st.button(f"✅ Generate {mode.upper()} (Upload Flow)"):
            with st.spinner(f"Generating {mode.upper()}..."):
                outline_to_send = copy.deepcopy(outline_preview)
                outline_to_send["title"] = new_title_upload.strip() if new_title_upload else outline_to_send["title"]

                endpoint = f"{BACKEND_URL}/generate-ppt" if mode == "ppt" else f"{BACKEND_URL}/generate-doc"
                file_resp = requests.post(endpoint, json={"outline": outline_to_send}, timeout=180)
                if file_resp.status_code == 200:
                    filename = extract_filename_from_cd(file_resp) or (
                        "presentation.pptx" if mode == "ppt" else "document.docx"
                    )

                    st.success(f"✅ {mode.upper()} generated successfully!")
                    st.download_button(
                        f"⬇️ Download {mode.upper()}",
                        data=file_resp.content if file_resp.content else b"",
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                             if mode == "ppt"
                             else "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"download_upload_{mode}_{filename}"
                    )

                    st.session_state.generated_files.append({
                        "type": mode,
                        "filename": filename,
                        "content": file_resp.content,
                    })
                else:
                    st.error(f"❌ Generation failed: {file_resp.status_code} — {file_resp.text}")

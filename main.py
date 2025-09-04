# main.py
import os
import tempfile
from typing import List

import fitz  # PyMuPDF
import docx
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mistralai import Mistral

# --------------------
# Config
# --------------------
# Read your key from env. Example (PowerShell):
#   $env:MISTRAL_API_KEY="your_real_key"
MISTRAL_API_KEY = "MEo5qeq34xziFnYgqpKhxtIW50tbCzQa"

SUMMARY_INSTRUCTION = (
    "Provide a comprehensive and detailed summary of the given content. "
    "Ensure that no important point, topic, or detail is omitted. "
    "Cover every aspect thoroughly, maintaining accuracy and completeness. "
    "The summary should be as extensive as possible, preserving the depth "
    "and context of the original material rather than condensing it too much."
)

# Conservative character limits to keep requests reliable
CHUNK_CHARS = 8000
CHUNK_OVERLAP = 300
MODEL_NAME = "mistral-small-latest"

# --------------------
# FastAPI app
# --------------------
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------
# Utils: extraction
# --------------------
def extract_text(path: str, filename: str) -> str:
    name = filename.lower()

    if name.endswith(".pdf"):
        text_parts: List[str] = []
        doc = fitz.open(path)
        try:
            for page in doc:
                # "text" ensures plain text extraction
                text_parts.append(page.get_text("text"))
        finally:
            doc.close()
        return "\n".join(text_parts)

    if name.endswith(".docx"):
        d = docx.Document(path)
        return "\n".join(p.text for p in d.paragraphs)

    if name.endswith(".txt"):
        # Try common encodings, then ignore errors as last resort
        for enc in ("utf-8", "utf-16", "utf-16-le", "utf-16-be", "latin-1"):
            try:
                with open(path, "r", encoding=enc) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    return ""


def split_text(text: str, chunk_size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Simple character-based chunking with overlap to avoid boundary loss."""
    if not text:
        return []
    chunks: List[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        chunks.append(text[start:end])
        if end == n:
            break
        start = max(0, end - overlap)
    return chunks


# --------------------
# Utils: Mistral calls
# --------------------
def get_mistral_client() -> Mistral:
    if not MISTRAL_API_KEY:
        raise HTTPException(status_code=500, detail="Mistral API key not set (MISTRAL_API_KEY).")
    return Mistral(api_key=MISTRAL_API_KEY)


def call_mistral(text: str, system_instruction: str) -> str:
    """Single chat completion call."""
    client = get_mistral_client()
    resp = client.chat.complete(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": text},
        ],
    )
    return resp.choices[0].message.content


def summarize_long_text(full_text: str) -> str:
    """
    Map-reduce style summarization without LangChain:
      1) Summarize each chunk exhaustively (map)
      2) Merge all chunk summaries into one comprehensive summary (reduce)
    """
    # 1) Map
    chunks = split_text(full_text)
    if len(chunks) <= 1:
        return call_mistral(full_text, SUMMARY_INSTRUCTION)

    per_chunk_instruction = (
        "You are given a chunk from a longer document.\n"
        "Write a meticulous, exhaustive summary of this chunk. Retain all important "
        "points, facts, numbers, definitions, lists, examples, equations, and names. "
        "Avoid generalities; do not omit details."
    )
    partial_summaries: List[str] = []
    for idx, ch in enumerate(chunks, 1):
        mapped = call_mistral(ch, per_chunk_instruction)
        partial_summaries.append(f"Chunk {idx} Summary:\n{mapped}")

    # 2) Reduce (single pass). If your docs are huge, you can add a second-level reduce here.
    combined = "\n\n".join(partial_summaries)

    reduce_instruction = (
        SUMMARY_INSTRUCTION
        + "\n\nYou are given multiple detailed chunk summaries of the same document. "
          "Merge them into a single unified summary that:\n"
          "- Preserves every important detail from the chunk summaries\n"
          "- Resolves overlaps and contradictions carefully\n"
          "- Organizes content logically with clear sections and bullet points where helpful\n"
          "- Maintains accuracy, specificity, and completeness throughout"
    )
    return call_mistral(combined, reduce_instruction)


# --------------------
# Routes
# --------------------
@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_NAME}

@app.post("/upload/")
async def upload(file: UploadFile = File(...)):
    """
    Upload a document, extract text, and immediately return a comprehensive summary.
    (Matches your Streamlit flow that calls /upload and expects 'summary' in the response.)
    """
    # Save to a temp file to let extractors (PDF/DOCX) work reliably
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        text = extract_text(tmp_path, file.filename)
    finally:
        # Clean up the temp file
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Unsupported, empty, or unreadable file content.")

    try:
        summary = summarize_long_text(text)
    except HTTPException:
        # Re-raise known HTTP errors (e.g., missing API key)
        raise
    except Exception as e:
        # Convert SDK or other runtime issues to a clean 502
        raise HTTPException(status_code=502, detail=f"Summarization failed: {e}")

    return {
        "filename": file.filename,
        "chars": len(text),
        "chunks": len(split_text(text)),
        "summary": summary,
    }

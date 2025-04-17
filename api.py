import os
import json
import base64
import datetime
import re
import numpy as np
import faiss
from openai import OpenAI
from flask import Flask, request, jsonify
from flask_cors import CORS
from docx import Document

__version__ = "v1.0.7-test"
print(f"\U0001F680 API Version: {__version__}")

# === Helper: Convert **bold** to real bold in Word ===
def add_markdown_bold(paragraph, text):
    parts = re.split(r'(\*\*[^*]+\*\*)', text)
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        else:
            paragraph.add_run(part)

# === API Keys ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
print("\U0001F512 OPENAI_API_KEY exists?", bool(OPENAI_API_KEY))
client = OpenAI(api_key=OPENAI_API_KEY)

# === Flask App Setup ===
app = Flask(__name__)
CORS(app, origins=["https://www.aivs.uk"])

@app.after_request
def apply_cors_headers(response):
    response.headers.add("Access-Control-Allow-Origin", "https://www.aivs.uk")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type")
    response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
    return response

@app.route("/ping", methods=["POST", "OPTIONS"])
def ping():
    if request.method == "OPTIONS":
        return '', 204
    return jsonify({"message": "pong"})

# === FAISS Index Loader ===
try:
    faiss_index = faiss.read_index("faiss_index/police_chunks.index")
    with open("faiss_index/police_metadata.json", "r", encoding="utf-8") as f:
        metadata = json.load(f)
    print("\u2705 FAISS index and metadata loaded.")
except Exception as e:
    faiss_index = None
    metadata = []
    print("\u26A0\uFE0F Failed to load FAISS index:", str(e))

# === GPT Logic ===
def ask_gpt_with_context(query, context):
    prompt = f"""
You are a police procedural administrator using UK law and internal operational guidance.

**Supporting Evidence:**
{context}

**Question:**
{query}

**Analysis:**
- Explain what the evidence implies.
- List 2–4 clear actions the staff should take.
- Flag any compliance or reporting issues.
"""
    completion = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    return completion.choices[0].message.content.strip()

@app.route("/query", methods=["POST", "OPTIONS"])
def query():
    if request.method == "OPTIONS":
        return '', 204

    data = request.json
    query_text = data.get("query", "")
    full_name = data.get("full_name", "Anonymous")
    supervisor_name = data.get("supervisor_name", "Supervisor")
    timestamp = datetime.datetime.utcnow().strftime("%d %B %Y, %H:%M GMT")

    print(f"\U0001F4E5 Received query from {full_name}: {query_text}")

    # === FAISS Context ===
    if faiss_index:
        query_vector = client.embeddings.create(
            input=[query_text.replace("\n", " ")],
            model="text-embedding-3-small"
        ).data[0].embedding

        D, I = faiss_index.search(np.array([query_vector]).astype("float32"), 5)

        matched_chunks = []
        for i in I[0]:
            chunk_file = metadata[i]["chunk_file"]
            with open(f"data/{chunk_file}", "r", encoding="utf-8") as f:
                matched_chunks.append(f.read().strip())

        context = "\n\n---\n\n".join(matched_chunks)

        print("\U0001F50D FAISS matched files:")
        for i in I[0]:
            print(" -", metadata[i]["chunk_file"])
    else:
        context = "Policy lookup not available (FAISS index not loaded)."

    # === GPT ===
    answer = ask_gpt_with_context(query_text, context)
    print(f"\U0001F9E0 GPT answer: {answer[:80]}...")

    # === Ensure output folder exists ===
    os.makedirs("output", exist_ok=True)

    # === Word Output Only (No Email) ===
    doc_path = f"output/{full_name.replace(' ', '_')}.docx"

    doc = Document()
    doc.add_heading(f"Response for {full_name}", level=1)
    doc.add_paragraph(f"\U0001F4C5 Generated: {timestamp}")

    doc.add_heading("Supporting Evidence", level=2)
    doc.add_paragraph(context)

    doc.add_heading("AI Analysis", level=2)
    add_markdown_bold(doc.add_paragraph(), answer)

    doc.save(doc_path)
    print(f"\U0001F4C4 Word saved: {doc_path}")

    return jsonify({
        "status": "ok",
        "message": "✅ Test mode: GPT response generated from FAISS context.",
        "context_preview": context[:200]
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

""import os
import json
import base64
import numpy as np
import faiss
from openai import OpenAI
from flask import Flask, request, jsonify
from flask_cors import CORS
from docx import Document
from postmarker.core import PostmarkClient
from datetime import datetime

# === Configuration ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
POSTMARK_API_TOKEN = os.getenv("POSTMARK_API_TOKEN")

# === OpenAI client ===
print("🔐 OPENAI_API_KEY exists?", bool(OPENAI_API_KEY))
client = OpenAI(api_key=OPENAI_API_KEY)

# === FAISS index and metadata ===
faiss_index = faiss.read_index("faiss_index/police_chunks.index")
with open("faiss_index/police_metadata.json", "r", encoding="utf-8") as f:
    metadata = json.load(f)

def get_chunk_text(fname):
    path = os.path.join("data", fname)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except:
        return "[Missing chunk text]"

# === Flask setup ===
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

# === GPT logic with merged context and analysis ===
def ask_gpt_with_context(query, context):
    prompt = f"""
You are a police procedural assistant using UK law and operational guidance.

### SUPPORTING EVIDENCE:
{context}

### QUESTION:
{query}

### ANALYSIS:
- Provide a clear summary of what the evidence implies.
- Recommend next steps or actions.
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

    # Timestamp the response
    timestamp = datetime.utcnow().strftime("%d %B %Y, %H:%M GMT")
    data = request.json
    query_text = data.get("query", "")
    full_name = data.get("full_name", "Anonymous")
    user_email = data.get("email")
    supervisor_email = data.get("supervisor_email")
    hr_email = data.get("hr_email")

    print(f"📥 Received query from {full_name}: {query_text}")

    # === Real FAISS lookup ===
    query_vector = client.embeddings.create(
        input=[query_text.replace("\n", " ")],
        model="text-embedding-3-small"
    ).data[0].embedding

    D, I = faiss_index.search(np.array([query_vector]).astype("float32"), 5)
    chunks = [get_chunk_text(metadata[i]["chunk_file"]) for i in I[0]]
    context = "\n\n---\n\n".join(chunks)

    print("🔍 FAISS matched files:")
    for i in I[0]:
        print(f" - {metadata[i]['chunk_file']}")

    # Run GPT with real context
    merged_response = ask_gpt_with_context(query_text, context)
    print(f"🧠 GPT response: {merged_response[:80]}...")

    os.makedirs("output", exist_ok=True)

    # === Generate Word doc ===
    doc_path = f"output/{full_name.replace(' ', '_')}.docx"
    doc = Document()
    doc.add_heading(f"Response for {full_name}", level=1)
    doc.add_paragraph(f"🕒 Generated: {timestamp}")
    doc.add_paragraph("")
    doc.add_paragraph(merged_response)
    doc.save(doc_path)

    # === Generate JSON file ===
    json_path = f"output/{full_name.replace(' ', '_')}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "query": query_text,
            "context": context,
            "response": merged_response,
            "timestamp": timestamp
        }, f, indent=2)

    # === Send emails ===
    postmark = PostmarkClient(server_token=POSTMARK_API_TOKEN)

    recipients = {
        "User": user_email,
        "Supervisor": supervisor_email,
        "HR": hr_email
    }

    for role, recipient in recipients.items():
        if not recipient:
            continue

        attachments = []

        for file_path, name, content_type in [
            (doc_path, f"{role}_response.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            (json_path, f"{role}_response.json", "application/json")
        ]:
            with open(file_path, "rb") as f:
                content = base64.b64encode(f.read()).decode("utf-8")
                attachments.append({
                    "Name": name,
                    "Content": content,
                    "ContentType": content_type
                })

        postmark.emails.send(
            From="michael@justresults.co",
            To=recipient,
            Subject=f"{role} Response: {full_name}",
            TextBody=f"Attached are your merged Word and JSON response files.",
            Attachments=attachments
        )

        print(f"📤 Sent merged response to {role} at {recipient}")

    return jsonify({"message": "✅ Merged emails sent with Word and JSON files."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

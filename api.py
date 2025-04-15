import json
import zipfile
import openai
import os

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))  # ✅ This is correct

import faiss
import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS
from docx import Document
from reportlab.pdfgen import canvas
from postmarker.core import PostmarkClient

# Flask app setup
app = Flask(__name__)
CORS(app, origins=["https://www.aivs.uk"])

# Load FAISS index + metadata
faiss_index = faiss.read_index("faiss_index/police_chunks.index")
with open("faiss_index/police_metadata.json", "r", encoding="utf-8") as f:
    metadata = json.load(f)

# Load Postmark API key
POSTMARK_API_TOKEN = os.getenv("POSTMARK_API_TOKEN")

# CORS headers for all responses
@app.after_request
def apply_cors_headers(response):
    response.headers.add("Access-Control-Allow-Origin", "https://www.aivs.uk")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type")
    response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
    return response

# Ping route for testing
@app.route("/ping", methods=["POST", "OPTIONS"])
def ping():
    if request.method == "OPTIONS":
        return '', 204
    print("✅ POST /ping received!")
    return jsonify({"message": "pong"})

# Utility: Load chunk file
def get_chunk_text(fname):
    path = os.path.join("data", fname)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except:
        return "[Chunk missing]"

# Utility: Create OpenAI embedding
def get_embedding(text):
    response = openai.embeddings.create(
        input=[text.replace("\n", " ")],
        model="text-embedding-3-small"
    )
    return response.data[0].embedding

# Utility: Ask GPT
def ask_gpt(query, context):
    prompt = f"""You are a police procedural assistant using UK law and operational guidance.

Answer the question below using the provided reference material.

### QUESTION:
{query}

### CONTEXT:
{context}

### ANSWER:"""

    completion = openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    return completion.choices[0].message.content.strip()

# Main /query endpoint
@app.route("/query", methods=["POST", "OPTIONS"])
def query():
    if request.method == "OPTIONS":
        return '', 204

    data = request.json
    query_text = data.get("query", "")
    user_email = data.get("email")
    supervisor_email = data.get("supervisor_email")
    hr_email = data.get("hr_email")
    full_name = data.get("full_name", "Unknown")

    if not query_text or not user_email:
        return jsonify({"error": "Missing query or user email"}), 400

    print(f"📥 Received query from {full_name}: {query_text}")

    # Run FAISS
    query_vector = get_embedding(query_text)
    D, I = faiss_index.search(np.array([query_vector]).astype("float32"), 5)
    chunks = [get_chunk_text(metadata[i]["chunk_file"]) for i in I[0]]
    context = "\n\n---\n\n".join(chunks)

    # Ask GPT
    answer = ask_gpt(query_text, context)
    print(f"🧠 GPT: {answer[:80]}...")

    # Create ZIP output folder
    os.makedirs("output", exist_ok=True)
    zip_path = f"output/response_{full_name.replace(' ', '_')}.zip"

    with zipfile.ZipFile(zip_path, "w") as zipf:
        for role, recipient in {
            "User": user_email,
            "Supervisor": supervisor_email,
            "HR": hr_email
        }.items():
            if not recipient:
                continue

            # Create Word doc
            doc_path = f"output/{role}.docx"
            doc = Document()
            doc.add_heading(f"{role} Response", 0)
            doc.add_paragraph(answer)
            doc.save(doc_path)
            zipf.write(doc_path, arcname=f"{role}.docx")

            # Create PDF
            pdf_path = f"output/{role}.pdf"
            c = canvas.Canvas(pdf_path)
            c.drawString(100, 800, f"{role} Response:")
            for i, line in enumerate(answer.splitlines()):
                c.drawString(100, 780 - (i * 14), line[:100])
            c.save()
            zipf.write(pdf_path, arcname=f"{role}.pdf")

    # Email ZIP using Postmark
    client = PostmarkClient(server_token=POSTMARK_API_TOKEN)
    with open(zip_path, "rb") as f:
        zip_data = f.read()

    for role, recipient in {
        "User": user_email,
        "Supervisor": supervisor_email,
        "HR": hr_email
    }.items():
        if recipient:
            client.emails.send(
                From="noreply@aivs.uk",
                To=recipient,
                Subject=f"{role} Response: {full_name}",
                TextBody=f"Attached is the {role} response to the query.",
                Attachments=[
                    {
                        "Name": os.path.basename(zip_path),
                        "Content": zip_data.encode("base64"),
                        "ContentType": "application/zip"
                    }
                ]
            )
            print(f"📤 Sent ZIP to {role} at {recipient}")

    return jsonify({"message": "✅ Emails sent!"})

# Run app locally if needed
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
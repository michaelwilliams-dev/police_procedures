import os
import os.path
import json
import base64
import datetime
import re
import numpy as np
import faiss
import requests
from openai import OpenAI
from flask import Flask, request, jsonify
from flask_cors import CORS
from docx import Document

__version__ = "v1.0.7-test"
print(f"🚀 API Version: {__version__}")

def add_markdown_bold(paragraph, text):
    parts = re.split(r'(\*\*[^*]+\*\*)', text)
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        else:
            paragraph.add_run(part)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
print("🔒 OPENAI_API_KEY exists?", bool(OPENAI_API_KEY))
client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)
CORS(app, origins=["https://www.aivs.uk"])

@app.route('/')
def index():
    return "Welcome to the Police Procedures API"

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

try:
    faiss_index = faiss.read_index("faiss_index/police_chunks.index")
    with open("faiss_index/police_metadata.json", "r", encoding="utf-8") as f:
        metadata = json.load(f)
    print("✅ FAISS index and metadata loaded.")
except Exception as e:
    faiss_index = None
    metadata = []
    print("⚠️ Failed to load FAISS index:", str(e))
### START HERE
def ask_gpt_with_context(data, context):
    query = data.get("query", "")
    job_title = data.get("job_title", "Not specified")
    rank_level = data.get("rank_level", "Not specified")
    timeline = data.get("timeline", "Not specified")
    discipline = data.get("discipline", "Not specified")
    site = data.get("site", "Not specified")
    funnel_1 = data.get("funnel_1", "Not specified")
    funnel_2 = data.get("funnel_2", "Not specified")
    funnel_3 = data.get("funnel_3", "Not specified")

    prompt = f"""
You are responding to an internal police procedures query via a secure reporting system.

All responses must:
- Be based on UK law, police operational guidance, and internal procedures only.
- Include British spelling, tone, and regulatory references.

### Enquiry:
"{query}"

### Context from FAISS Index:
{context}

### Enquirer Details:
- Job Title: {job_title}
- Rank Level: {rank_level}
- Timeline: {timeline}
- Discipline: {discipline}
- Site: {site}

### Additional Focus:
- Support Need: {funnel_1}
- Current Status: {funnel_2}
- Follow-Up Expectation: {funnel_3}

### Your Task:
Please generate a structured response that includes:

1. **Enquirer Reply** – in plain English, appropriate for the rank level.
2. **Action Sheet** – bullet-point steps the enquirer should follow.
3. **Policy Notes** – cite any relevant UK policing policies, SOPs, or legal codes.
"""

    completion = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    return completion.choices[0].message.content.strip()

### HERE
def send_email_mailjet(to_emails, subject, body_text, attachments=[], timestamp=None):
   
    MAILJET_API_KEY = os.getenv("MJ_APIKEY_PUBLIC")
    MAILJET_SECRET_KEY = os.getenv("MJ_APIKEY_PRIVATE")

    message = {
        "Messages": [{
            "From": {
                "Email": "noreply@securemaildrop.uk",
                "Name": "Secure Maildrop"
            },
            "To": to_emails,
            
            "Subject": subject,
            "TextPart": body_text,
            "HTMLPart": f"<pre>{body_text}</pre>",
            "Attachments": [
                {
                    "ContentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "Filename": os.path.basename(file_path),
                    "Base64Content": base64.b64encode(open(file_path, "rb").read()).decode()
                }
                for file_path in attachments
            ]
        }]
    }

    response = requests.post(
        "https://api.mailjet.com/v3.1/send",
        auth=(MAILJET_API_KEY, MAILJET_SECRET_KEY),
        json=message
    )

    print(f"📤 Mailjet status: {response.status_code}")
    print(response.json())

@app.route("/query", methods=["POST", "OPTIONS"])
def query_handler():
    if request.method == "OPTIONS":
        return '', 204

    data = request.json
    query_text = data.get("query", "")
    full_name = data.get("full_name", "Anonymous")
    supervisor_name = data.get("supervisor_name", "Supervisor")
    user_email = data.get("email")
    supervisor_email = data.get("supervisor_email")
    hr_email = data.get("hr_email")
    timestamp = datetime.datetime.utcnow().strftime("%d %B %Y, %H:%M GMT")

    print(f"📥 Received query from {full_name}: {query_text}")

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

        print("🔍 FAISS matched files:")
        for i in I[0]:
            print(" -", metadata[i]["chunk_file"])
    else:
        context = "Policy lookup not available (FAISS index not loaded)."

    answer = ask_gpt_with_context(data, context)

    print(f"🧠 GPT answer: {answer[:80]}...")

    os.makedirs("output", exist_ok=True)

    doc_path = f"output/{full_name.replace(' ', '_')}_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.docx"

    doc = Document()
    doc.add_heading(f"Response for {full_name}", level=1)
    
    doc.add_paragraph(f"📅 Generated: {timestamp}")


    doc.add_heading("AI Analysis", level=2)
    add_markdown_bold(doc.add_paragraph(), answer)

    doc.add_heading("Supporting Evidence", level=2)
    doc.add_paragraph(context)

    doc.save(doc_path)
    print(f"📄 Word saved: {doc_path}")

    # Compile list of recipients with names Replace == 0901
    recipients = []
    if user_email:
        recipients.append({"Email": user_email, "Name": full_name})
    if supervisor_email:
        recipients.append({"Email": supervisor_email, "Name": supervisor_name})
    if hr_email:
        recipients.append({"Email": hr_email, "Name": "HR Department"})

    if not recipients:
        return jsonify({"error": "No valid email addresses provided."}), 400

    subject = f"AI Analysis for {full_name} - {timestamp}"
    body_text = f"""To: {full_name},

    Please find attached the AI-generated analysis based on your query submitted on {timestamp}.
    """
    status, response = send_email_mailjet(
        to_emails=recipients,
        subject=subject,
        body_text=body_text,
        attachments=[doc_path]
      
    )

    return jsonify({
        "status": "ok",
        "message": "✅ GPT response generated and email sent to recipients.",
        "context_preview": context[:200],
        "mailjet_status": status,
        "mailjet_response": response
    })

# Run App
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
import os
import json
import base64

# === Change 1028 ===
import datetime

__version__ = "v1.0.3 – 17 April 2025 – GPT structured + placeholder context"
print(f"🚀 API Version: {__version__}")
from openai import OpenAI
from flask import Flask, request, jsonify
from flask_cors import CORS
from docx import Document
from postmarker.core import PostmarkClient

# === Configuration ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
POSTMARK_API_TOKEN = os.getenv("POSTMARK_API_TOKEN")

# === OpenAI client ===
print("🔐 OPENAI_API_KEY exists?", bool(OPENAI_API_KEY))
client = OpenAI(api_key=OPENAI_API_KEY)

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

# === GPT logic ===
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

# === Change 1135 ===
    full_name = data.get("full_name", "Anonymous")

    timestamp = datetime.datetime.utcnow().strftime("%d %B %Y, %H:%M GMT")

    user_email = data.get("email")
    supervisor_email = data.get("supervisor_email")
    hr_email = data.get("hr_email")

    print(f"📥 Received query from {full_name}: {query_text}")

    
    context = "Policy lookup not available. FAISS context will be restored soon."
    answer = ask_gpt_with_context(query_text, context)
    print(f"🧠 GPT answer: {answer[:80]}...")

    os.makedirs("output", exist_ok=True)

    # === Generate Word doc ===
    doc_path = f"output/{full_name.replace(' ', '_')}.docx"
    doc = Document()
    doc.add_heading(f"Response for {full_name}", level=1)
    doc.add_paragraph("📄 AUTOMATED CASE REVIEW\n\n" + answer)
    doc.save(doc_path)

    # === Generate JSON file ===
    # === Change 1047 ===
    #json_path = f"output/{full_name.replace(' ', '_')}.json"
    #with open(json_path, "w", encoding="utf-8") as f:
    #    json.dump({"full_name": full_name, "query": query_text, "answer": answer}, f, indent=2)

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

        # === Change 1201 ===
        attachments = []

        for file_path, name, content_type in [
            (doc_path, f"{role}_response.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        ]:
            with open(file_path, "rb") as f:
                content = base64.b64encode(f.read()).decode("utf-8")
                attachments.append({
                    "Name": name,
                    "Content": content,
                    "ContentType": content_type
                })

        # === Change 1210 ===
        final_text = f"Attached are your Word document.\n\n📅 Generated: {timestamp}"
        print("📧 Final TextBody:\n" + final_text)

        # === Change 1224 ===   
        postmark.emails.send(
            From="michael@justresults.co",
            To=recipient,
            Subject=f"{role} Response: {full_name}",
            HtmlBody=f"""
                <p>Attached is your Word document.</p>
                <p><strong>📅 Generated:</strong> {timestamp}</p>
            """,
            Attachments=attachments
        )

        print(f"📤 Sent Word + JSON to {role} at {recipient}")

    return jsonify({"message": "✅ Emails sent with Word and JSON files."})
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
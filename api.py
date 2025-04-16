import os
import json
import base64
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

# === GPT logic with merged context and analysis ===
def ask_gpt_with_context(query, context):
    prompt = f"""
You are a police procedural assistant using UK law and operational guidance.

### CONTEXT:
{context}

### QUESTION:
{query}

### INSTRUCTIONS:
- First, display the CONTEXT as 'Supporting Evidence'
- Then, write a clear, well-structured ANALYSIS
- Use bullet points or paragraphs where appropriate

### RESPONSE:
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
    user_email = data.get("email")
    supervisor_email = data.get("supervisor_email")
    hr_email = data.get("hr_email")

    print(f"📥 Received query from {full_name}: {query_text}")

    # Placeholder for context (normally from FAISS)
    simulated_context = "- Policy 11.2 states CCTV must be reviewed within 24 hours.\n- Missing footage must be reported to senior staff and IT."

    # Run GPT
    merged_response = ask_gpt_with_context(query_text, simulated_context)
    print(f"🧠 GPT response: {merged_response[:80]}...")

    os.makedirs("output", exist_ok=True)

    # === Generate Word doc ===
    doc_path = f"output/{full_name.replace(' ', '_')}.docx"
    doc = Document()
    doc.add_heading(f"Response for {full_name}", level=1)
    doc.add_paragraph(merged_response)
    doc.save(doc_path)

    # === Generate JSON file ===
    json_path = f"output/{full_name.replace(' ', '_')}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "query": query_text,
            "context": simulated_context,
            "response": merged_response
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

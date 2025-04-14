from flask import Flask, request, jsonify
import openai
import faiss
import numpy as np
import json
import os

# Config
openai.api_key = os.getenv("OPENAI_API_KEY")
embedding_model = "text-embedding-3-small"
gpt_model = "gpt-4"

# Load index and metadata
faiss_index = faiss.read_index("faiss_index/police_chunks.index")
with open("faiss_index/police_metadata.json", "r", encoding="utf-8") as f:
    metadata = json.load(f)

# Optional: load text chunks from files
def get_chunk_text(fname):
    path = os.path.join("data", fname)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except:
        return "[Chunk missing]"

# Embedding function
def get_embedding(text):
    response = openai.embeddings.create(
        input=[text.replace("\n", " ")],
        model=embedding_model
    )
    return response.data[0].embedding

# GPT function
def ask_gpt(query, context):
    prompt = f"""You are a police procedural assistant using UK law and operational guidance.

Answer the question below using the provided reference material.

### QUESTION:
{query}

### CONTEXT:
{context}

### ANSWER:"""

    completion = openai.chat.completions.create(
        model=gpt_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    return completion.choices[0].message.content.strip()

# Flask app
app = Flask(__name__)

@app.route("/query", methods=["POST"])
def query():
    data = request.json
    query_text = data.get("query", "")

    if not query_text:
        return jsonify({"error": "Missing 'query' field"}), 400

    query_vector = get_embedding(query_text)
    D, I = faiss_index.search(np.array([query_vector]).astype("float32"), 5)

    chunks = [get_chunk_text(metadata[i]["chunk_file"]) for i in I[0]]
    context = "\n\n---\n\n".join(chunks)
    answer = ask_gpt(query_text, context)

    return jsonify({
        "answer": answer,
        "chunks": chunks,
        "matched_files": [metadata[i]["chunk_file"] for i in I[0]]
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

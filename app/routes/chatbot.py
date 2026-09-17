import os

import google.generativeai as genai
from flask import Blueprint, current_app, jsonify, render_template, request, session
from flask_login import current_user, login_required

from app.models.document import Document
from app.routes.analysis import analyze_file

chatbot_bp = Blueprint("chatbot", __name__)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel(
    "gemini-2.5-flash-lite",
    generation_config={
        "temperature": 0.7,
        "max_output_tokens": 120,
        "top_p": 0.9,
    },
)


@chatbot_bp.route("/chat")
@login_required
def chat():

    documents = (
        Document.query.filter_by(user_id=current_user.id)
        .order_by(Document.upload_date.desc())
        .all()
    )

    if "chat_history" not in session:
        session["chat_history"] = []

    return render_template(
        "chatbot/chatbot.html",
        documents=documents,
    )


@chatbot_bp.route("/chat/ask", methods=["POST"])
@login_required
def ask():

    question = request.form.get("question", "").strip()
    document_id = request.form.get("document_id")

    if not question:
        return jsonify({"answer": "Type a message."})

    q = question.lower().strip()

    quick = {
        "hi": "Hey 😊",
        "hello": "Hello there!😄",
        "hey": "Hey what's up! 😄",
        "thanks": "Anytime ✨",
        "thank you": "You're welcome ✨",
        "bye": "See you later! 👋",
        "ok": "Got it 👍",
        "okay": "Alright 👍",
    }

    if q in quick:
        return jsonify({"answer": quick[q]})

    document_context = ""

    if document_id:

        document = Document.query.filter_by(
            id=document_id,
            user_id=current_user.id,
        ).first()

        if document:

            upload_folder = os.path.join(
                current_app.root_path,
                "static",
                "uploads",
            )

            file_path = os.path.join(
                upload_folder,
                document.filename,
            )

            result = analyze_file(file_path)

            document_context = result.get("text", "")[:2500]

    history = session.get("chat_history", [])

    history_text = ""

    for msg in history[-6:]:
        history_text += f"{msg['role']}: {msg['text']}\n"

    prompt = f"""
You are LegalLens AI.

Style:
- Reply naturally like ChatGPT.
- Keep replies under 3 sentences unless asked.
- Don't greet every message.
- Answer any topic.
- Use document only if relevant.
- Continue the conversation naturally.

Conversation:
{history_text}

Document:
{document_context}

User:
{question}
"""

    try:

        response = model.generate_content(prompt)

        answer = response.text.strip()

    except Exception:
        answer = "Couldn't generate a response right now."

    history.append({"role": "User", "text": question})
    history.append({"role": "Assistant", "text": answer})

    session["chat_history"] = history[-12:]
    session.modified = True

    return jsonify({"answer": answer})

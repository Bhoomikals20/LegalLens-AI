import httpx2
from google import genai
from google.genai import errors, types
from flask import Blueprint, current_app, jsonify, render_template, request, session
from flask_login import current_user, login_required

from app.models.document import Document
from app.routes.analysis import analyze_file
from app.utils.document_storage import get_document_file_path

chatbot_bp = Blueprint("chatbot", __name__)


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
        username=current_user.full_name,
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

    api_key = current_app.config.get("GEMINI_API_KEY")
    if isinstance(api_key, str):
        api_key = api_key.strip()

    if not api_key:
        return jsonify({"answer": "Chat is unavailable until GEMINI_API_KEY is configured."}), 503

    document_context = ""

    if document_id:
        try:
            selected_document_id = int(document_id)
        except (TypeError, ValueError):
            return jsonify({"answer": "The selected document is unavailable."}), 404

        document = Document.query.filter_by(
            id=selected_document_id,
            user_id=current_user.id,
        ).first()
        if document is None:
            return jsonify({"answer": "The selected document is unavailable."}), 404

        try:
            file_path = get_document_file_path(document)
        except (FileNotFoundError, ValueError):
            return jsonify({"answer": "The selected document is unavailable."}), 404

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
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=120,
                top_p=0.9,
            ),
        )
    except errors.APIError as error:
        current_app.logger.warning(
            "Gemini request failed with API status %s.", error.code
        )

        if error.code in (401, 403):
            answer = (
                "Gemini rejected the configured API key or model access. "
                "Check the key and Google AI Studio project permissions."
            )
        elif error.code == 404:
            answer = "The configured Gemini model is unavailable. Please check the model configuration."
        elif error.code == 429:
            answer = "Gemini's rate limit has been reached. Please wait a moment and try again."
        elif isinstance(error.code, int) and error.code >= 500:
            answer = "The AI provider is temporarily unavailable. Please try again."
        else:
            answer = "Gemini could not process this request. Please try again."

        return jsonify({"answer": answer}), 503
    except httpx2.HTTPError as error:
        current_app.logger.warning(
            "Gemini request failed with transport error %s.",
            type(error).__name__,
        )
        return jsonify(
            {"answer": "The AI provider could not be reached. Please try again."}
        ), 503

    answer = (response.text or "").strip()
    if not answer:
        return jsonify({"answer": "The AI service returned an empty response."}), 502

    history.append({"role": "User", "text": question})
    history.append({"role": "Assistant", "text": answer})

    session["chat_history"] = history[-12:]
    session.modified = True

    return jsonify({"answer": answer})

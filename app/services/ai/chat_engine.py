import re

from app.services.ai.clause_detector import detect_clauses
from app.services.ai.summarizer import generate_summary


def find_sentence(text, keyword):
    """Return the first sentence containing a keyword."""

    sentences = re.split(r"(?<=[.!?])\s+", text)

    for sentence in sentences:
        if keyword.lower() in sentence.lower():
            return sentence.strip()

    return None


def answer_question(question, text):
    """
    Offline document question-answer engine.
    """

    if not text:
        return "No readable text was found in this document."

    question = question.lower()

    # Summary
    if any(
        word in question
        for word in [
            "summary",
            "summarize",
            "overview",
        ]
    ):
        return generate_summary(text)

    # Payment
    if "payment" in question:
        result = find_sentence(text, "payment")
        return result or "No payment clause was found."

    # Termination
    if "termination" in question:
        result = find_sentence(text, "termination")
        return result or "No termination clause was found."

    # Confidentiality
    if "confidential" in question or "nda" in question:
        result = find_sentence(text, "confidential")
        return result or "No confidentiality clause was found."

    # Governing law
    if "law" in question or "jurisdiction" in question:
        result = find_sentence(text, "governing law") or find_sentence(
            text, "jurisdiction"
        )
        return result or "No governing law clause was found."

    # Dates
    if "date" in question:
        dates = re.findall(
            r"(?:January|February|March|April|May|June|July|August|"
            r"September|October|November|December)\s+\d{1,2},?\s+\d{4}"
            r"|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}",
            text,
            flags=re.IGNORECASE,
        )

        if dates:
            return "Dates found: " + ", ".join(dict.fromkeys(dates))

        return "No important dates were found."

    # Clause questions
    if "clause" in question:
        clauses = detect_clauses(text)

        if clauses:
            names = ", ".join(clause["name"] for clause in clauses)
            return f"Detected clauses: {names}"

        return "No predefined clauses were detected."

    # Default search
    keywords = re.findall(r"\b[a-z]{4,}\b", question)

    for keyword in keywords:
        sentence = find_sentence(text, keyword)
        if sentence:
            return sentence

    return (
        "I couldn't find an exact answer in the document. "
        "Try asking about payment, termination, confidentiality, "
        "dates, summary, or governing law."
    )

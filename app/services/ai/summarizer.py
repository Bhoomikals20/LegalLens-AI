import re


def clean_text(text):
    """Normalize extracted text."""

    if not text:
        return ""

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def split_sentences(text):
    """Split text into approximate sentences."""

    text = clean_text(text)

    if not text:
        return []

    sentences = re.split(
        r"(?<=[.!?])\s+",
        text,
    )

    return [sentence.strip() for sentence in sentences if len(sentence.strip()) > 20]


def generate_summary(text, max_sentences=5):
    """
    Generate a fast extractive summary.

    This version does not use an external AI API.
    """

    sentences = split_sentences(text)

    if not sentences:
        return "No sufficient readable text was available to generate a summary."

    selected = sentences[:max_sentences]

    return " ".join(selected)


def extract_key_information(text):
    """
    Extract simple dates, monetary values and contact-like information.
    """

    if not text:
        return {
            "dates": [],
            "amounts": [],
        }

    dates = re.findall(
        r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
        r"|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
        r"|(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2},?\s+\d{4})\b",
        text,
        flags=re.IGNORECASE,
    )

    amounts = re.findall(
        r"(?:₹|Rs\.?|INR|\$|USD|€|EUR|£|GBP)\s?" r"\d[\d,]*(?:\.\d{1,2})?",
        text,
        flags=re.IGNORECASE,
    )

    return {
        "dates": list(dict.fromkeys(dates))[:20],
        "amounts": list(dict.fromkeys(amounts))[:20],
    }

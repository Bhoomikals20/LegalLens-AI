import re

CLAUSES = {
    "Payment": [
        "payment",
        "pay",
        "paid",
        "fee",
        "amount due",
        "invoice",
        "compensation",
    ],
    "Termination": [
        "termination",
        "terminate",
        "termination date",
        "terminate this agreement",
    ],
    "Confidentiality": [
        "confidential",
        "confidentiality",
        "non-disclosure",
        "nda",
        "trade secret",
    ],
    "Liability": [
        "liability",
        "liable",
        "damages",
        "indemnify",
        "indemnification",
    ],
    "Governing Law": [
        "governing law",
        "jurisdiction",
        "laws of",
    ],
    "Renewal": [
        "renewal",
        "renew",
        "automatically renew",
        "extension",
    ],
    "Notice": [
        "notice",
        "written notice",
        "notification",
    ],
    "Obligations": [
        "obligation",
        "shall",
        "must",
        "responsible for",
        "duties",
    ],
    "Dispute Resolution": [
        "dispute",
        "arbitration",
        "mediation",
        "dispute resolution",
    ],
    "Intellectual Property": [
        "intellectual property",
        "copyright",
        "trademark",
        "patent",
        "ownership of intellectual property",
    ],
}


def detect_clauses(text):
    """
    Detect important clauses using keyword matching.
    """

    if not text:
        return []

    text_lower = text.lower()
    detected = []

    for clause_name, keywords in CLAUSES.items():

        matches = []

        for keyword in keywords:

            if re.search(re.escape(keyword), text_lower):
                matches.append(keyword)

        if matches:

            detected.append(
                {
                    "name": clause_name,
                    "status": "Detected",
                    "matches": matches[:5],
                }
            )

    return detected

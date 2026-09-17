import re

RISK_RULES = [
    {
        "name": "Broad Liability",
        "level": "High",
        "keywords": [
            "unlimited liability",
            "unlimited damages",
            "liable for all damages",
        ],
        "reason": "The document may impose broad or potentially unlimited liability.",
    },
    {
        "name": "Indemnification",
        "level": "High",
        "keywords": [
            "indemnify",
            "indemnification",
            "hold harmless",
        ],
        "reason": "Indemnification obligations may create significant financial exposure.",
    },
    {
        "name": "Automatic Renewal",
        "level": "Medium",
        "keywords": [
            "automatically renew",
            "automatic renewal",
            "shall automatically renew",
        ],
        "reason": "Automatic renewal may continue the agreement unless cancellation requirements are followed.",
    },
    {
        "name": "Termination Restriction",
        "level": "Medium",
        "keywords": [
            "may not terminate",
            "cannot terminate",
            "non-cancellable",
        ],
        "reason": "The document may restrict the ability to terminate the agreement.",
    },
    {
        "name": "Late Payment",
        "level": "Medium",
        "keywords": [
            "late fee",
            "late payment",
            "interest on overdue",
        ],
        "reason": "Late payment provisions may create additional financial obligations.",
    },
    {
        "name": "Confidentiality Obligation",
        "level": "Low",
        "keywords": [
            "confidential information",
            "confidentiality",
        ],
        "reason": "The document contains obligations concerning confidential information.",
    },
]


def analyze_risks(text):
    """
    Detect potentially risky provisions.

    This is a rule-based first version and should not be
    treated as legal advice.
    """

    if not text:
        return []

    text_lower = text.lower()

    risks = []

    for rule in RISK_RULES:

        found = False

        for keyword in rule["keywords"]:

            if re.search(
                re.escape(keyword),
                text_lower,
            ):
                found = True
                break

        if found:

            risks.append(
                {
                    "name": rule["name"],
                    "level": rule["level"],
                    "reason": rule["reason"],
                }
            )

    return risks


def calculate_risk_score(risks):
    """
    Calculate an overall indicative risk score.
    """

    score = 0

    for risk in risks:

        if risk["level"] == "High":
            score += 30

        elif risk["level"] == "Medium":
            score += 15

        else:
            score += 5

    return min(
        score,
        100,
    )

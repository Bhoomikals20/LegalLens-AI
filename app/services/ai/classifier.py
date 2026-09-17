import re


def classify_document(text):
    """
    Classify a document using keyword-based document patterns.
    """

    if not text:
        return {
            "type": "Unknown Document",
            "confidence": 0,
            "description": "No readable text was available for classification.",
        }

    text_lower = text.lower()

    categories = {
        "Contract / Agreement": [
            "agreement",
            "contract",
            "party",
            "parties",
            "hereinafter",
            "terms and conditions",
            "termination",
            "whereas",
            "obligations",
            "effective date",
        ],
        "Will / Testament": [
            "last will",
            "last will and testament",
            "testament",
            "executor",
            "beneficiary",
            "bequeath",
            "inheritance",
            "estate",
        ],
        "Lease / Rental Agreement": [
            "lease agreement",
            "landlord",
            "tenant",
            "rent",
            "rental property",
            "security deposit",
            "premises",
        ],
        "Employment Agreement": [
            "employment agreement",
            "employee",
            "employer",
            "salary",
            "job title",
            "employment",
            "termination of employment",
        ],
        "Non-Disclosure Agreement": [
            "non-disclosure agreement",
            "nda",
            "confidential information",
            "confidentiality",
            "disclosing party",
            "receiving party",
        ],
        "Recommendation Letter": [
            "recommendation letter",
            "to whom it may concern",
            "i highly recommend",
            "research assistant",
            "academic performance",
            "personality",
        ],
        "Medical Document": [
            "patient",
            "diagnosis",
            "medical",
            "hospital",
            "clinical",
            "doctor",
            "audiology",
            "audiologist",
            "prescription",
            "treatment",
            "medical report",
            "hearing loss",
        ],
        "Invoice / Financial Document": [
            "invoice",
            "tax invoice",
            "amount due",
            "subtotal",
            "total amount",
            "tax",
            "payment due",
        ],
    }

    scores = {}

    for category, keywords in categories.items():

        score = 0

        for keyword in keywords:
            score += len(
                re.findall(
                    re.escape(keyword),
                    text_lower,
                )
            )

        scores[category] = score

    best_category = max(scores, key=scores.get)
    best_score = scores[best_category]

    if best_score == 0:
        return {
            "type": "Other Document",
            "confidence": 30,
            "description": "The document could not be confidently matched to a known document category.",
        }

    confidence = min(95, 45 + (best_score * 5))

    descriptions = {
        "Contract / Agreement": "A document containing contractual terms, obligations or agreements between parties.",
        "Will / Testament": "A testamentary document describing the distribution of assets and wishes of an individual.",
        "Lease / Rental Agreement": "A document defining rental, tenancy and property-related obligations.",
        "Employment Agreement": "A document defining employment terms, responsibilities, compensation and conditions.",
        "Non-Disclosure Agreement": "A confidentiality agreement concerning the protection and use of confidential information.",
        "Medical Document": "A medical or healthcare-related document containing patient, diagnostic or treatment information.",
        "Invoice / Financial Document": "A financial document containing billing, payment or transaction information.",
    }

    return {
        "type": best_category,
        "confidence": confidence,
        "description": descriptions.get(
            best_category,
            "Document category identified from its contents.",
        ),
    }

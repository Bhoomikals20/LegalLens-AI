from app.services.ai.clause_detector import CLAUSES, detect_clauses

CLAUSE_IMPORTANCE = {
    "Payment": "Defines payment obligations and due amounts.",
    "Termination": "Explains how either party can end the agreement.",
    "Confidentiality": "Protects sensitive information.",
    "Liability": "Defines responsibility for damages.",
    "Governing Law": "Specifies which country's or state's laws apply.",
    "Renewal": "Explains contract renewal conditions.",
    "Notice": "Defines how official notices must be given.",
    "Obligations": "Clarifies responsibilities of each party.",
    "Dispute Resolution": "Explains how disputes will be handled.",
    "Intellectual Property": "Protects ownership of created work.",
}


def detect_missing_clauses(text):
    """
    Compare detected clauses against expected clauses.
    """

    detected = detect_clauses(text)

    detected_names = {clause["name"] for clause in detected}

    missing = []

    for clause in CLAUSES.keys():

        if clause not in detected_names:

            missing.append(
                {
                    "name": clause,
                    "importance": CLAUSE_IMPORTANCE.get(
                        clause, "Important legal protection."
                    ),
                }
            )

    return missing

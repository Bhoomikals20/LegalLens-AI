def generate_recommendations(
    document_type,
    risk_score,
    missing_clauses,
    risks,
):
    """
    Generate practical recommendations based on
    detected risks and missing clauses.
    """

    recommendations = []

    # Missing clauses
    for clause in missing_clauses:

        recommendations.append(
            {
                "title": f"Add {clause['name']} Clause",
                "priority": "Medium",
                "description": clause["importance"],
            }
        )

    # High-risk clauses
    for risk in risks:

        recommendations.append(
            {
                "title": f"Review {risk['name']}",
                "priority": risk["level"],
                "description": risk["reason"],
            }
        )

    # Overall risk advice
    if risk_score is not None:

        if risk_score >= 60:

            recommendations.insert(
                0,
                {
                    "title": "Seek Legal Review",
                    "priority": "High",
                    "description": (
                        "This document contains multiple high-risk provisions."
                    ),
                },
            )

        elif risk_score >= 30:

            recommendations.insert(
                0,
                {
                    "title": "Review Before Signing",
                    "priority": "Medium",
                    "description": (
                        "Check highlighted clauses carefully before proceeding."
                    ),
                },
            )

    # Document-specific advice
    if document_type == "Employment Agreement":

        recommendations.append(
            {
                "title": "Verify Salary & Notice Period",
                "priority": "Low",
                "description": (
                    "Ensure compensation and notice period match your expectations."
                ),
            }
        )

    elif document_type == "Lease / Rental Agreement":

        recommendations.append(
            {
                "title": "Check Security Deposit",
                "priority": "Low",
                "description": ("Verify refund conditions for the security deposit."),
            }
        )

    elif document_type == "Contract / Agreement":

        recommendations.append(
            {
                "title": "Confirm Obligations",
                "priority": "Low",
                "description": (
                    "Ensure responsibilities of both parties are clearly defined."
                ),
            }
        )

    return recommendations

import os
import re
import difflib

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from flask_login import current_user, login_required

from app.models.document import Document
from app.routes.analysis import analyze_file

compare_bp = Blueprint("compare", __name__)


def normalize_text(text):
    """
    Normalize extracted text before comparison.
    Removes excessive spaces and empty lines.
    """

    if not text:
        return ""

    lines = []

    for line in text.splitlines():

        line = re.sub(r"\s+", " ", line).strip()

        if line:
            lines.append(line)

    return "\n".join(lines)


def get_paragraphs(text):
    """
    Convert extracted text into meaningful comparison blocks.
    """

    text = normalize_text(text)

    if not text:
        return []

    paragraphs = [
        paragraph.strip() for paragraph in re.split(r"\n+", text) if paragraph.strip()
    ]

    return paragraphs


def calculate_similarity(text1, text2):
    """
    Calculate overall textual similarity percentage.
    """

    if not text1 and not text2:
        return 100.0

    if not text1 or not text2:
        return 0.0

    matcher = difflib.SequenceMatcher(
        None,
        text1.lower(),
        text2.lower(),
    )

    return round(matcher.ratio() * 100, 1)


def compare_paragraphs(paragraphs1, paragraphs2):
    """
    Compare paragraphs and return actual changes.
    """

    matcher = difflib.SequenceMatcher(
        None,
        paragraphs1,
        paragraphs2,
        autojunk=False,
    )

    changes = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():

        if tag == "equal":
            continue

        if tag == "delete":

            for paragraph in paragraphs1[i1:i2]:

                changes.append(
                    {
                        "type": "removed",
                        "old": paragraph,
                        "new": "",
                    }
                )

        elif tag == "insert":

            for paragraph in paragraphs2[j1:j2]:

                changes.append(
                    {
                        "type": "added",
                        "old": "",
                        "new": paragraph,
                    }
                )

        elif tag == "replace":

            old_items = paragraphs1[i1:i2]
            new_items = paragraphs2[j1:j2]

            max_length = max(
                len(old_items),
                len(new_items),
            )

            for index in range(max_length):

                old_text = old_items[index] if index < len(old_items) else ""

                new_text = new_items[index] if index < len(new_items) else ""

                if old_text and new_text:

                    changes.append(
                        {
                            "type": "modified",
                            "old": old_text,
                            "new": new_text,
                        }
                    )

                elif old_text:

                    changes.append(
                        {
                            "type": "removed",
                            "old": old_text,
                            "new": "",
                        }
                    )

                elif new_text:

                    changes.append(
                        {
                            "type": "added",
                            "old": "",
                            "new": new_text,
                        }
                    )

    return changes


def compare_documents(document1, document2):
    """
    Extract and compare the contents of two documents.
    """

    upload_folder = os.path.join(
        current_app.root_path,
        "static",
        "uploads",
    )

    file_path1 = os.path.join(
        upload_folder,
        document1.filename,
    )

    file_path2 = os.path.join(
        upload_folder,
        document2.filename,
    )

    if not os.path.exists(file_path1):
        raise FileNotFoundError(f"Document not found: {document1.filename}")

    if not os.path.exists(file_path2):
        raise FileNotFoundError(f"Document not found: {document2.filename}")

    # Use the SAME extraction system used by Analysis.
    result1 = analyze_file(file_path1)
    result2 = analyze_file(file_path2)

    text1 = normalize_text(result1.get("text", ""))

    text2 = normalize_text(result2.get("text", ""))

    paragraphs1 = get_paragraphs(text1)
    paragraphs2 = get_paragraphs(text2)

    similarity = calculate_similarity(
        text1,
        text2,
    )

    changes = compare_paragraphs(
        paragraphs1,
        paragraphs2,
    )

    added_count = sum(1 for change in changes if change["type"] == "added")

    removed_count = sum(1 for change in changes if change["type"] == "removed")

    modified_count = sum(1 for change in changes if change["type"] == "modified")

    return {
        "similarity": similarity,
        "document1": {
            "words": len(text1.split()),
            "characters": len(text1),
            "paragraphs": len(paragraphs1),
            "method": result1.get("method"),
            "ocr_used": result1.get("ocr_used"),
        },
        "document2": {
            "words": len(text2.split()),
            "characters": len(text2),
            "paragraphs": len(paragraphs2),
            "method": result2.get("method"),
            "ocr_used": result2.get("ocr_used"),
        },
        "changes": changes,
        "added_count": added_count,
        "removed_count": removed_count,
        "modified_count": modified_count,
        "total_changes": len(changes),
    }


@compare_bp.route(
    "/compare",
    methods=["GET", "POST"],
)
@login_required
def compare():

    documents = (
        Document.query.filter_by(user_id=current_user.id)
        .order_by(Document.upload_date.desc())
        .all()
    )

    document1 = None
    document2 = None
    comparison = None

    if request.method == "POST":

        document1_id = request.form.get("document1")

        document2_id = request.form.get("document2")

        if not document1_id or not document2_id:

            flash(
                "Please select two documents.",
                "warning",
            )

            return redirect(url_for("compare.compare"))

        if document1_id == document2_id:

            flash(
                "Please select two different documents.",
                "warning",
            )

            return redirect(url_for("compare.compare"))

        document1 = Document.query.filter_by(
            id=document1_id,
            user_id=current_user.id,
        ).first_or_404()

        document2 = Document.query.filter_by(
            id=document2_id,
            user_id=current_user.id,
        ).first_or_404()

        try:

            comparison = compare_documents(
                document1,
                document2,
            )

        except Exception as error:

            current_app.logger.exception("Document comparison failed")

            flash(
                "Unable to compare the selected documents. "
                "Please check that both files are readable.",
                "danger",
            )

            return redirect(url_for("compare.compare"))

    return render_template(
        "compare/compare.html",
        documents=documents,
        document1=document1,
        document2=document2,
        comparison=comparison,
        compared=comparison is not None,
    )

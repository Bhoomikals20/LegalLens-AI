from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.models.document import Document

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    # Get all uploaded documents of the logged-in user
    documents = (
        Document.query.filter_by(user_id=current_user.id)
        .order_by(Document.upload_date.desc())
        .all()
    )

    # Total document count
    document_count = len(documents)

    return render_template(
        "dashboard/dashboard.html",
        document_count=document_count,
        documents=documents,
    )

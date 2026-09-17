import os

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
    send_from_directory,
)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.document import Document

upload_bp = Blueprint("upload", __name__)

ALLOWED_EXTENSIONS = {
    "pdf",
    "docx",
    "txt",
    "png",
    "jpg",
    "jpeg",
}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@upload_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():

    if request.method == "POST":

        if "document" not in request.files:
            flash("No file selected.", "danger")
            return redirect(url_for("upload.upload"))

        file = request.files["document"]

        if file.filename == "":
            flash("Please choose a file.", "warning")
            return redirect(url_for("upload.upload"))

        if not allowed_file(file.filename):
            flash("Unsupported file type.", "danger")
            return redirect(url_for("upload.upload"))

        filename = secure_filename(file.filename)

        upload_folder = os.path.join(
            current_app.root_path,
            "static",
            "uploads",
        )

        os.makedirs(upload_folder, exist_ok=True)

        filepath = os.path.join(upload_folder, filename)

        file.save(filepath)

        document = Document(
            user_id=current_user.id,
            filename=filename,
            original_filename=file.filename,
            file_type=filename.rsplit(".", 1)[1].lower(),
            file_size=os.path.getsize(filepath),
        )

        db.session.add(document)
        db.session.commit()

        flash(
            "Document uploaded successfully!",
            "success",
        )

        return redirect(url_for("upload.upload"))

    documents = (
        Document.query.filter_by(user_id=current_user.id)
        .order_by(Document.upload_date.desc())
        .all()
    )

    return render_template(
        "upload/upload.html",
        documents=documents,
    )


@upload_bp.route("/preview/<int:document_id>")
@login_required
def preview(document_id):

    document = Document.query.filter_by(
        id=document_id, user_id=current_user.id
    ).first_or_404()

    upload_folder = os.path.join(
        current_app.root_path,
        "static",
        "uploads",
    )

    return send_from_directory(
        upload_folder,
        document.filename,
    )


@upload_bp.route("/delete/<int:document_id>")
@login_required
def delete_document(document_id):

    document = Document.query.filter_by(
        id=document_id, user_id=current_user.id
    ).first_or_404()

    upload_folder = os.path.join(
        current_app.root_path,
        "static",
        "uploads",
    )

    filepath = os.path.join(
        upload_folder,
        document.filename,
    )

    if os.path.exists(filepath):
        os.remove(filepath)

    db.session.delete(document)
    db.session.commit()

    flash(
        "Document deleted successfully.",
        "success",
    )

    return redirect(url_for("upload.upload"))

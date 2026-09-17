from app.extensions import db


class Document(db.Model):

    __tablename__ = "documents"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
    )

    filename = db.Column(
        db.String(255),
        nullable=False,
    )

    original_filename = db.Column(
        db.String(255),
        nullable=False,
    )

    file_type = db.Column(
        db.String(30),
    )

    file_size = db.Column(
        db.BigInteger,
    )

    upload_date = db.Column(
        db.DateTime,
        server_default=db.func.now(),
    )

    status = db.Column(
        db.String(30),
        default="Uploaded",
    )
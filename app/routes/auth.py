from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
)

from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user,
)

from app.extensions import db, bcrypt
from app.models.user import User

auth_bp = Blueprint("auth", __name__)


# -----------------------------
# LOGIN
# -----------------------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("dashboard.dashboard"))

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        if user and bcrypt.check_password_hash(
            user.password,
            password,
        ):

            login_user(user)

            

            return redirect(
             url_for("dashboard.dashboard")
            )

        flash(
            "Invalid email or password.",
            "danger",
        )

    return render_template("auth/login.html")


# -----------------------------
# REGISTER
# -----------------------------
@auth_bp.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        full_name = request.form["full_name"]
        email = request.form["email"]
        password = request.form["password"]

        existing = User.query.filter_by(email=email).first()

        if existing:

            flash(
                "Email already registered.",
                "warning",
            )

            return redirect(
                url_for("auth.register")
            )

        hashed_password = bcrypt.generate_password_hash(
            password
        ).decode("utf-8")

        user = User(
            full_name=full_name,
            email=email,
            password=hashed_password,
        )

        db.session.add(user)
        db.session.commit()

        flash(
            "Registration successful. Please login.",
            "success",
        )

        return redirect(
            url_for("auth.login")
        )

    return render_template("auth/register.html")


# -----------------------------
# LOGOUT
# -----------------------------
@auth_bp.route("/logout")
@login_required
def logout():

    logout_user()

    
    

    return redirect(
        url_for("auth.login")
    )
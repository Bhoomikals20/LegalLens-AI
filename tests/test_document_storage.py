import tempfile
import unittest
from io import BytesIO
from pathlib import Path
import re
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import sqlalchemy as sa
import fitz
import httpx2
from docx import Document as WordDocument
from google.genai import errors
from PIL import Image

from app import create_app
from app.extensions import bcrypt, db
from app.models.document import Document
from app.models.user import User
from config import Config


class DocumentStorageTests(unittest.TestCase):
    def setUp(self):
        self.upload_directory = tempfile.TemporaryDirectory()
        self.database_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.database_directory.name) / "tests.sqlite"
        with patch.object(
            Config, "SECRET_KEY", "test-secret-key-for-storage-tests"
        ), patch.object(
            Config, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{database_path}"
        ):
            self.app = create_app()

        self.app.config.update(
            TESTING=True,
            UPLOAD_FOLDER=self.upload_directory.name,
            GEMINI_API_KEY="test-gemini-api-key",
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            self.assertEqual(db.engine.url.drivername, "sqlite")
            db.create_all()
            self.owner_id = self._create_user("owner@example.com")
            self.other_user_id = self._create_user("other@example.com")

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        self.upload_directory.cleanup()
        self.database_directory.cleanup()

    def _create_user(self, email):
        user = User(full_name=email.split("@")[0], email=email, password="unused")
        db.session.add(user)
        db.session.commit()
        return user.id

    def _create_document(self, owner_id, filename, original_filename):
        document = Document(
            user_id=owner_id,
            filename=filename,
            original_filename=original_filename,
            file_type=Path(filename).suffix.lstrip("."),
            file_size=10,
        )
        db.session.add(document)
        db.session.commit()
        return document.id

    def _login(self, user_id):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True

    def _csrf_token(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        match = re.search(
            rb'<meta name="csrf-token" content="([^"]+)"', response.data
        )
        response.close()
        self.assertIsNotNone(match)
        return match.group(1).decode("ascii")

    def test_owner_preview_and_download_and_other_user_denied(self):
        stored_name = f"{uuid4().hex}.txt"
        private_file = Path(self.upload_directory.name) / stored_name
        private_file.write_text("private document", encoding="utf-8")

        with self.app.app_context():
            document_id = self._create_document(
                self.owner_id, stored_name, "Original Contract.txt"
            )

        self._login(self.owner_id)
        preview = self.client.get(f"/preview/{document_id}")
        download = self.client.get(f"/download/{document_id}")

        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.data, b"private document")
        self.assertIn("inline", preview.headers["Content-Disposition"])
        preview.close()
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.data, b"private document")
        self.assertIn("attachment", download.headers["Content-Disposition"])
        self.assertIn(
            "Original_Contract.txt", download.headers["Content-Disposition"]
        )
        download.close()

        self.client.get("/logout")
        self._login(self.other_user_id)
        self.assertEqual(self.client.get(f"/preview/{document_id}").status_code, 404)
        self.assertEqual(self.client.get(f"/download/{document_id}").status_code, 404)

    def test_unauthenticated_invalid_and_missing_file_requests(self):
        with self.app.app_context():
            missing_id = self._create_document(
                self.owner_id, f"{uuid4().hex}.txt", "missing.txt"
            )
            traversal_id = self._create_document(
                self.owner_id, "../outside.txt", "outside.txt"
            )

        self.assertEqual(self.client.get(f"/preview/{missing_id}").status_code, 302)
        self.assertEqual(self.client.get(f"/download/{missing_id}").status_code, 302)
        self.assertEqual(self.client.get("/preview/999999").status_code, 302)
        self.assertEqual(self.client.get("/download/999999").status_code, 302)
        self.assertEqual(self.client.get("/preview/not-an-id").status_code, 404)

        self._login(self.owner_id)
        self.assertEqual(self.client.get("/preview/999999").status_code, 404)
        self.assertEqual(self.client.get("/download/999999").status_code, 404)
        self.assertEqual(self.client.get(f"/preview/{missing_id}").status_code, 404)
        self.assertEqual(self.client.get(f"/download/{missing_id}").status_code, 404)
        self.assertEqual(self.client.get(f"/preview/{traversal_id}").status_code, 404)
        self.assertEqual(self.client.get(f"/download/{traversal_id}").status_code, 404)

    def test_legacy_file_is_owner_checked_and_not_publicly_served(self):
        legacy_name = f"legacy-{uuid4().hex}.txt"
        legacy_directory = Path(self.app.root_path) / "static" / "uploads"
        legacy_directory.mkdir(parents=True, exist_ok=True)
        legacy_file = legacy_directory / legacy_name
        legacy_file.write_text("legacy document", encoding="utf-8")
        self.addCleanup(lambda: legacy_file.unlink(missing_ok=True))

        with self.app.app_context():
            document_id = self._create_document(
                self.owner_id, legacy_name, "Legacy Document.txt"
            )

        self.assertEqual(
            self.client.get(f"/static/uploads/{legacy_name}").status_code, 404
        )
        self.assertEqual(
            self.client.get(
                f"/static/other/../uploads/{legacy_name}"
            ).status_code,
            404,
        )

        self._login(self.owner_id)
        preview = self.client.get(f"/preview/{document_id}")
        self.assertEqual(preview.data, b"legacy document")
        preview.close()
        download = self.client.get(f"/download/{document_id}")
        self.assertEqual(download.data, b"legacy document")
        download.close()

    def test_upload_uses_private_uuid_filename_and_preserves_original_name(self):
        self._login(self.owner_id)
        csrf_token = self._csrf_token("/upload")
        response = self.client.post(
            "/upload",
            data={
                "csrf_token": csrf_token,
                "document": (
                    BytesIO(b"new document"),
                    "My Contract.txt",
                )
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            document = Document.query.filter_by(user_id=self.owner_id).one()
            self.assertEqual(document.original_filename, "My Contract.txt")
            self.assertRegex(document.filename, r"^[0-9a-f]{32}\.txt$")
            private_file = Path(self.upload_directory.name) / document.filename
            self.assertTrue(private_file.is_file())
            self.assertFalse(
                (Path(self.app.static_folder) / "uploads" / document.filename).exists()
            )

    def test_upload_accepts_supported_formats_and_rejects_mismatched_content(self):
        pdf = fitz.open()
        page = pdf.new_page()
        page.insert_text((72, 72), "A valid PDF document for upload testing.")
        files = {"pdf": pdf.tobytes()}
        pdf.close()

        docx = WordDocument()
        docx.add_paragraph("A valid DOCX document for upload testing.")
        docx_bytes = BytesIO()
        docx.save(docx_bytes)
        files["docx"] = docx_bytes.getvalue()
        files["txt"] = b"A valid plain-text document."

        for extension, image_format in (("png", "PNG"), ("jpg", "JPEG"), ("jpeg", "JPEG")):
            image_bytes = BytesIO()
            Image.new("RGB", (20, 20), color="white").save(
                image_bytes, format=image_format
            )
            files[extension] = image_bytes.getvalue()

        self._login(self.owner_id)
        csrf_token = self._csrf_token("/upload")
        for extension, content in files.items():
            with self.subTest(extension=extension):
                response = self.client.post(
                    "/upload",
                    data={
                        "csrf_token": csrf_token,
                        "document": (BytesIO(content), f"valid.{extension}"),
                    },
                    content_type="multipart/form-data",
                )
                self.assertEqual(response.status_code, 302)
                response.close()

        with self.app.app_context():
            documents = Document.query.filter_by(user_id=self.owner_id).all()
            self.assertEqual(len(documents), len(files))
            self.assertEqual(
                {document.file_type for document in documents},
                set(files),
            )
            self.assertTrue(
                all(
                    (Path(self.upload_directory.name) / document.filename).is_file()
                    for document in documents
                )
            )

        response = self.client.post(
            "/upload",
            data={
                "csrf_token": csrf_token,
                "document": (BytesIO(b"not a PDF"), "invalid.pdf"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 302)
        response.close()
        with self.app.app_context():
            self.assertEqual(
                Document.query.filter_by(user_id=self.owner_id).count(),
                len(files),
            )

    def test_analysis_reads_private_upload(self):
        stored_name = f"{uuid4().hex}.txt"
        private_file = Path(self.upload_directory.name) / stored_name
        private_file.write_text(
            "This Agreement includes payment terms and obligations.",
            encoding="utf-8",
        )

        with self.app.app_context():
            document_id = self._create_document(
                self.owner_id, stored_name, "Private Agreement.txt"
            )

        self._login(self.owner_id)
        response = self.client.get(f"/analysis/{document_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"payment terms", response.data)
        self.assertIn(b"Document Classification", response.data)
        self.assertIn(b"AI Summary", response.data)
        self.assertIn(b"Detected Clauses", response.data)
        self.assertIn(b"Missing Clauses", response.data)
        self.assertIn(b"AI Recommendations", response.data)
        self.assertNotIn(b"```", response.data)
        response.close()

    def test_analysis_does_not_report_missing_legal_clauses_for_invoices(self):
        stored_name = f"{uuid4().hex}.txt"
        private_file = Path(self.upload_directory.name) / stored_name
        private_file.write_text(
            "Invoice total amount due is $250.00.",
            encoding="utf-8",
        )

        with self.app.app_context():
            document_id = self._create_document(
                self.owner_id, stored_name, "Invoice.txt"
            )

        self._login(self.owner_id)
        response = self.client.get(f"/analysis/{document_id}")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invoice / Financial Document", response.data)
        self.assertIn(
            b"Clause analysis is available for supported legal agreements.",
            response.data,
        )
        self.assertIn(
            b"Risk analysis is available for supported legal agreements.",
            response.data,
        )
        self.assertIn(
            b"Recommendations are available for supported legal agreements.",
            response.data,
        )
        self.assertNotIn(b"Add Termination Clause", response.data)
        self.assertNotIn(b"No important clauses appear to be missing.", response.data)
        response.close()

    def test_analysis_uses_ocr_for_uploaded_images(self):
        stored_name = f"{uuid4().hex}.png"
        image_path = Path(self.upload_directory.name) / stored_name
        Image.new("RGB", (40, 40), color="white").save(image_path)

        with self.app.app_context():
            document_id = self._create_document(
                self.owner_id, stored_name, "Scanned Agreement.png"
            )

        self._login(self.owner_id)
        with patch(
            "app.routes.analysis.pytesseract.image_to_data",
            return_value={
                "text": ["Agreement", "payment"],
                "conf": ["95", "90"],
            },
        ) as image_to_data:
            response = self.client.get(f"/analysis/{document_id}")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Tesseract OCR", response.data)
        self.assertIn(b"Agreement payment", response.data)
        self.assertIn(b"OCR", response.data)
        image_to_data.assert_called_once()
        response.close()

    def test_analysis_extracts_pdf_and_docx_text(self):
        pdf = fitz.open()
        page = pdf.new_page()
        pdf_text = (
            "This agreement establishes payment and termination terms between "
            "the parties for the full duration of this sample contract."
        )
        page.insert_text((72, 72), pdf_text)
        pdf_path = Path(self.upload_directory.name) / f"{uuid4().hex}.pdf"
        pdf.save(pdf_path)
        pdf.close()

        docx_text = (
            "This employment agreement explains salary, responsibilities, "
            "notice requirements, and other terms for both parties."
        )
        docx = WordDocument()
        docx.add_paragraph(docx_text)
        docx_path = Path(self.upload_directory.name) / f"{uuid4().hex}.docx"
        docx.save(docx_path)

        with self.app.app_context():
            document_ids = [
                self._create_document(
                    self.owner_id, pdf_path.name, "Selectable Agreement.pdf"
                ),
                self._create_document(
                    self.owner_id, docx_path.name, "Employment Agreement.docx"
                ),
            ]

        self._login(self.owner_id)
        for document_id, expected_text, expected_method in (
            (document_ids[0], "establishes payment", "PDF Text Extraction"),
            (document_ids[1], "explains salary", "DOCX Text Extraction"),
        ):
            with self.subTest(method=expected_method):
                response = self.client.get(f"/analysis/{document_id}")
                self.assertEqual(response.status_code, 200)
                self.assertIn(expected_text.encode(), response.data)
                self.assertIn(expected_method.encode(), response.data)
                response.close()

    def test_chatbot_reads_private_upload(self):
        stored_name = f"{uuid4().hex}.txt"
        private_file = Path(self.upload_directory.name) / stored_name
        private_file.write_text("Document payment terms.", encoding="utf-8")

        with self.app.app_context():
            document_id = self._create_document(
                self.owner_id, stored_name, "Private Terms.txt"
            )

        self._login(self.owner_id)
        with patch(
            "app.routes.chatbot.analyze_file",
            return_value={"text": "Document payment terms."},
        ) as analyze_file, patch("app.routes.chatbot.genai.Client") as client_factory:
            client_factory.return_value.models.generate_content.return_value = (
                SimpleNamespace(text="Payment is due monthly.")
            )
            response = self.client.post(
                "/chat/ask",
                data={"question": "What are the payment terms?", "document_id": str(document_id)},
                headers={"X-CSRFToken": self._csrf_token("/chat")},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["answer"], "Payment is due monthly."
        )
        analyze_file.assert_called_once_with(str(private_file))
        client_factory.assert_called_once_with(api_key="test-gemini-api-key")
        client_factory.return_value.models.generate_content.assert_called_once()
        self.assertEqual(
            client_factory.return_value.models.generate_content.call_args.kwargs[
                "model"
            ],
            "gemini-3.5-flash-lite",
        )

    def test_chatbot_rejects_invalid_or_unowned_document_ids(self):
        self._login(self.owner_id)
        csrf_token = self._csrf_token("/chat")
        with patch("app.routes.chatbot.genai.Client") as client_factory:
            for document_id in ("not-an-id", "999999"):
                with self.subTest(document_id=document_id):
                    response = self.client.post(
                        "/chat/ask",
                        data={
                            "question": "Summarize this document",
                            "document_id": document_id,
                        },
                        headers={"X-CSRFToken": csrf_token},
                    )

                    self.assertEqual(response.status_code, 404)
                    self.assertEqual(
                        response.get_json()["answer"],
                        "The selected document is unavailable.",
                    )
                    response.close()
            client_factory.assert_not_called()

        with self.app.app_context():
            document_id = self._create_document(
                self.owner_id, f"{uuid4().hex}.txt", "Private.txt"
            )
        self._login(self.other_user_id)
        response = self.client.post(
            "/chat/ask",
            data={
                "question": "Summarize this document",
                "document_id": str(document_id),
            },
            headers={"X-CSRFToken": csrf_token},
        )
        self.assertEqual(response.status_code, 404)
        response.close()

    def test_chatbot_reports_missing_gemini_configuration(self):
        self._login(self.owner_id)
        self.app.config["GEMINI_API_KEY"] = None
        with patch("app.routes.chatbot.genai.Client") as client_factory:
            response = self.client.post(
                "/chat/ask",
                data={"question": "Can you explain this?"},
                headers={"X-CSRFToken": self._csrf_token("/chat")},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.get_json()["answer"],
            "Chat is unavailable until GEMINI_API_KEY is configured.",
        )
        client_factory.assert_not_called()

    def test_chatbot_surfaces_gemini_api_failure_without_details(self):
        self._login(self.owner_id)
        with patch("app.routes.chatbot.genai.Client") as client_factory:
            client_factory.return_value.models.generate_content.side_effect = (
                errors.APIError(
                    503,
                    {"error": {"message": "provider diagnostic detail"}},
                )
            )
            response = self.client.post(
                "/chat/ask",
                data={"question": "Explain a legal term."},
                headers={"X-CSRFToken": self._csrf_token("/chat")},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.get_json()["answer"],
            "The AI provider is temporarily unavailable. Please try again.",
        )
        self.assertNotIn(b"provider diagnostic detail", response.data)

    def test_chatbot_reports_gemini_configuration_and_quota_errors(self):
        self._login(self.owner_id)
        csrf_token = self._csrf_token("/chat")
        for status_code, expected_message in (
            (
                403,
                "Gemini rejected the configured API key or model access.",
            ),
            (
                429,
                "Gemini's rate limit has been reached.",
            ),
        ):
            with self.subTest(status_code=status_code):
                with patch("app.routes.chatbot.genai.Client") as client_factory:
                    client_factory.return_value.models.generate_content.side_effect = (
                        errors.APIError(
                            status_code,
                            {"error": {"message": "sensitive provider detail"}},
                        )
                    )
                    response = self.client.post(
                        "/chat/ask",
                        data={"question": "Explain a legal term."},
                        headers={"X-CSRFToken": csrf_token},
                    )

                self.assertEqual(response.status_code, 503)
                self.assertIn(
                    expected_message,
                    response.get_json()["answer"],
                )
                self.assertNotIn(b"sensitive provider detail", response.data)
                response.close()

    def test_chatbot_handles_gemini_transport_failures_without_details(self):
        self._login(self.owner_id)
        with patch("app.routes.chatbot.genai.Client") as client_factory:
            client_factory.return_value.models.generate_content.side_effect = (
                httpx2.ConnectError("sensitive transport detail")
            )
            response = self.client.post(
                "/chat/ask",
                data={"question": "Explain a legal term."},
                headers={"X-CSRFToken": self._csrf_token("/chat")},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.get_json()["answer"],
            "The AI provider could not be reached. Please try again.",
        )
        self.assertNotIn(b"sensitive transport detail", response.data)

    def test_comparison_reads_private_uploads(self):
        stored_names = [f"{uuid4().hex}.txt", f"{uuid4().hex}.txt"]
        private_files = [Path(self.upload_directory.name) / name for name in stored_names]
        for index, private_file in enumerate(private_files):
            private_file.write_text(f"Document text {index}.", encoding="utf-8")

        with self.app.app_context():
            document_ids = [
                self._create_document(self.owner_id, name, f"Document {index}.txt")
                for index, name in enumerate(stored_names)
            ]

        self._login(self.owner_id)
        with patch(
            "app.routes.compare.analyze_file",
            side_effect=[
                {"text": "First document text."},
                {"text": "Second document text."},
            ],
        ) as analyze_file:
            response = self.client.post(
                "/compare",
                data={
                    "csrf_token": self._csrf_token("/compare"),
                    "document1": str(document_ids[0]),
                    "document2": str(document_ids[1]),
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [call.args[0] for call in analyze_file.call_args_list],
            [str(path) for path in private_files],
        )
        response.close()

    def test_csrf_required_for_every_state_changing_route(self):
        self._login(self.owner_id)
        requests = [
            ("POST", "/login"),
            ("POST", "/register"),
            ("POST", "/upload"),
            ("POST", "/compare"),
            ("POST", "/chat/ask"),
            ("POST", "/logout"),
            ("POST", "/delete/1"),
        ]

        for method, path in requests:
            with self.subTest(method=method, path=path):
                response = self.client.open(path, method=method)
                self.assertEqual(response.status_code, 400)
                response.close()

        self.assertEqual(self.client.get("/logout").status_code, 405)
        self.assertEqual(self.client.get("/delete/1").status_code, 405)

    def test_missing_secret_key_prevents_app_startup(self):
        with patch.object(Config, "SECRET_KEY", None):
            with self.assertRaisesRegex(RuntimeError, "SECRET_KEY is required"):
                create_app()

    def test_registration_login_and_logout_require_valid_csrf_tokens(self):
        registration_token = self._csrf_token("/register")
        registration = self.client.post(
            "/register",
            data={
                "csrf_token": registration_token,
                "full_name": "CSRF Test",
                "email": "csrf-test@example.com",
                "password": "test-password",
            },
        )
        self.assertEqual(registration.status_code, 302)
        registration.close()

        login_token = self._csrf_token("/login")
        login = self.client.post(
            "/login",
            data={
                "csrf_token": login_token,
                "email": "csrf-test@example.com",
                "password": "test-password",
            },
        )
        self.assertEqual(login.status_code, 302)
        login.close()

        logout_token = self._csrf_token("/dashboard")
        logout = self.client.post(
            "/logout", data={"csrf_token": logout_token}
        )
        self.assertEqual(logout.status_code, 302)
        logout.close()

    def test_debug_mode_is_disabled_by_run_entry_point(self):
        run_source = (Path(__file__).parents[1] / "run.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("app.run(debug=False)", run_source)

    def test_document_delete_requires_csrf_and_removes_owned_file(self):
        stored_name = f"{uuid4().hex}.txt"
        private_file = Path(self.upload_directory.name) / stored_name
        private_file.write_text("delete me", encoding="utf-8")

        with self.app.app_context():
            document_id = self._create_document(
                self.owner_id, stored_name, "Delete Me.txt"
            )

        self._login(self.owner_id)
        csrf_token = self._csrf_token("/upload")
        response = self.client.post(
            f"/delete/{document_id}", data={"csrf_token": csrf_token}
        )

        self.assertEqual(response.status_code, 302)
        response.close()
        self.assertFalse(private_file.exists())
        with self.app.app_context():
            self.assertIsNone(db.session.get(Document, document_id))

    def test_chat_template_uses_text_nodes_and_includes_csrf(self):
        self._login(self.owner_id)
        response = self.client.get("/chat")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'name="csrf-token"', response.data)
        self.assertIn(b"textContent=String(text)", response.data)
        self.assertNotIn(b"innerHTML", response.data)
        self.assertIn(b"Hello owner", response.data)
        self.assertIn(b'appendMessage("assistant", data.answer', response.data)
        self.assertIn(b'id="sendButton"', response.data)
        self.assertIn(b"input.disabled=true", response.data)
        self.assertIn(b"input.disabled=false", response.data)
        self.assertIn(b'fetch("/chat/ask"', response.data)
        response.close()

    def test_dashboard_shows_owned_document_preview_and_download_actions(self):
        with self.app.app_context():
            document_id = self._create_document(
                self.owner_id, f"{uuid4().hex}.txt", "Dashboard File.txt"
            )

        self._login(self.owner_id)
        response = self.client.get("/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Dashboard File.txt", response.data)
        self.assertIn(f"/preview/{document_id}".encode(), response.data)
        self.assertIn(f"/download/{document_id}".encode(), response.data)
        response.close()

    def test_dashboard_settings_and_reports_navigation_routes(self):
        self._login(self.owner_id)
        response = self.client.get("/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'href="/settings"', response.data)
        self.assertIn(b'href="/reports"', response.data)
        self.assertEqual(self.client.get("/settings").status_code, 200)
        self.assertEqual(self.client.get("/reports").status_code, 200)
        response.close()

    def test_settings_requires_authentication_and_renders_account_details(self):
        self.assertEqual(self.client.get("/settings").status_code, 302)

        self._login(self.owner_id)
        response = self.client.get("/settings")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Profile information", response.data)
        self.assertIn(b"Change password", response.data)
        self.assertIn(b"Account information", response.data)
        self.assertIn(b"Sign out", response.data)
        self.assertIn(b"owner@example.com", response.data)
        self.assertIn(b"owner", response.data)
        response.close()

    def test_settings_profile_update_and_validation(self):
        self._login(self.owner_id)
        csrf_token = self._csrf_token("/settings")
        response = self.client.post(
            "/settings",
            data={
                "csrf_token": csrf_token,
                "action": "profile",
                "full_name": "Updated Owner",
                "email": "UPDATED@example.com",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Profile updated successfully.", response.data)
        response.close()

        with self.app.app_context():
            owner = db.session.get(User, self.owner_id)
            self.assertEqual(owner.full_name, "Updated Owner")
            self.assertEqual(owner.email, "updated@example.com")

        invalid_values = (
            {"full_name": "   ", "email": "valid@example.com"},
            {"full_name": "A" * 101, "email": "valid@example.com"},
            {"full_name": "Valid Name", "email": "not-an-email"},
        )
        for values in invalid_values:
            with self.subTest(values=values):
                response = self.client.post(
                    "/settings",
                    data={
                        "csrf_token": csrf_token,
                        "action": "profile",
                        **values,
                    },
                    follow_redirects=True,
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"Name is required", response.data) if not values["full_name"].strip() or len(values["full_name"]) > 100 else self.assertIn(b"valid email", response.data)
                response.close()

        response = self.client.post(
            "/settings",
            data={
                "csrf_token": csrf_token,
                "action": "profile",
                "full_name": "Owner",
                "email": "OTHER@example.com",
            },
            follow_redirects=True,
        )
        self.assertIn(b"already in use", response.data)
        response.close()

    def test_settings_password_change_verifies_and_hashes_password(self):
        with self.app.app_context():
            owner = db.session.get(User, self.owner_id)
            owner.password = bcrypt.generate_password_hash("current-password").decode("utf-8")
            db.session.commit()

        self._login(self.owner_id)
        csrf_token = self._csrf_token("/settings")
        invalid_passwords = (
            ("wrong-current", "new-password-123", "new-password-123", "Current password is incorrect."),
            ("current-password", "short", "short", "between 8 and 72 UTF-8 bytes"),
            ("current-password", "new-password-123", "different-password", "do not match"),
            ("current-password", "current-password", "current-password", "different from your current password"),
        )
        for current, new, confirm, message in invalid_passwords:
            with self.subTest(message=message):
                response = self.client.post(
                    "/settings",
                    data={
                        "csrf_token": csrf_token,
                        "action": "password",
                        "current_password": current,
                        "new_password": new,
                        "confirm_password": confirm,
                    },
                    follow_redirects=True,
                )
                self.assertIn(message.encode(), response.data)
                response.close()

        response = self.client.post(
            "/settings",
            data={
                "csrf_token": csrf_token,
                "action": "password",
                "current_password": "current-password",
                "new_password": "replacement-password",
                "confirm_password": "replacement-password",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Password changed successfully.", response.data)
        response.close()

        with self.app.app_context():
            updated = db.session.get(User, self.owner_id)
            self.assertNotEqual(updated.password, "replacement-password")
            self.assertTrue(
                bcrypt.check_password_hash(updated.password, "replacement-password")
            )
            self.assertFalse(
                bcrypt.check_password_hash(updated.password, "current-password")
            )

    def test_settings_logout_requires_csrf_and_ends_session(self):
        self._login(self.owner_id)
        self.assertEqual(self.client.get("/logout").status_code, 405)
        response = self.client.post("/logout")
        self.assertEqual(response.status_code, 400)
        response.close()

        csrf_token = self._csrf_token("/settings")
        response = self.client.post(
            "/logout",
            data={"csrf_token": csrf_token},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/settings").status_code, 302)
        response.close()

    def test_reports_list_and_generate_owner_scoped_document_report(self):
        stored_name = f"{uuid4().hex}.txt"
        private_file = Path(self.upload_directory.name) / stored_name
        private_file.write_text(
            "This agreement sets payment obligations and termination rights. "
            "The agreement includes notice and governing law requirements.",
            encoding="utf-8",
        )
        with self.app.app_context():
            document_id = self._create_document(
                self.owner_id, stored_name, "Report Agreement.txt"
            )
            other_document_id = self._create_document(
                self.other_user_id, f"{uuid4().hex}.txt", "Other User.txt"
            )

        self._login(self.owner_id)
        listing = self.client.get("/reports")
        self.assertEqual(listing.status_code, 200)
        self.assertIn(b"Report Agreement.txt", listing.data)
        self.assertNotIn(b"Other User.txt", listing.data)
        self.assertIn(f"/reports/{document_id}".encode(), listing.data)
        listing.close()

        report = self.client.get(f"/reports/{document_id}")
        self.assertEqual(report.status_code, 200)
        self.assertIn(b"Document Report", report.data)
        self.assertIn(b"Contract / Agreement", report.data)
        self.assertIn(b"Payment", report.data)
        self.assertIn(b"Print report", report.data)
        report.close()

        self._login(self.other_user_id)
        self.assertEqual(self.client.get(f"/reports/{document_id}").status_code, 404)
        self.assertEqual(self.client.get("/reports/999999").status_code, 404)
        self.assertGreater(other_document_id, 0)

    def test_report_for_document_with_missing_file_returns_404(self):
        with self.app.app_context():
            document_id = self._create_document(
                self.owner_id, f"{uuid4().hex}.txt", "Missing Report.txt"
            )
        self._login(self.owner_id)

        self.assertEqual(self.client.get(f"/reports/{document_id}").status_code, 404)

    def test_existing_database_migration_preserves_tables_and_records(self):
        with self.app.app_context():
            document = Document(
                user_id=self.owner_id,
                filename=f"{uuid4().hex}.txt",
                original_filename="Existing Record.txt",
                file_type="txt",
                file_size=20,
            )
            db.session.add(document)
            db.session.commit()
            document_id = document.id

        result = self.app.test_cli_runner().invoke(args=["db", "upgrade"])
        self.assertEqual(result.exit_code, 0, result.output)

        with self.app.app_context():
            self.assertIsNotNone(db.session.get(User, self.owner_id))
            preserved_document = db.session.get(Document, document_id)
            self.assertIsNotNone(preserved_document)
            self.assertEqual(
                preserved_document.original_filename, "Existing Record.txt"
            )
            self.assertIsNotNone(
                db.session.execute(
                    sa.text("SELECT version_num FROM alembic_version")
                ).scalar_one()
            )

    def test_fresh_database_is_created_by_migration_not_app_startup(self):
        with tempfile.TemporaryDirectory() as database_directory:
            database_path = Path(database_directory) / "fresh.sqlite"
            with patch.object(
                Config, "SECRET_KEY", "test-secret-key-for-migration-tests"
            ), patch.object(
                Config, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{database_path}"
            ):
                fresh_app = create_app()
            fresh_app.config.update(
                TESTING=True,
            )

            with fresh_app.app_context():
                self.assertEqual(
                    set(sa.inspect(db.engine).get_table_names()), set()
                )

            result = fresh_app.test_cli_runner().invoke(args=["db", "upgrade"])
            self.assertEqual(result.exit_code, 0, result.output)

            with fresh_app.app_context():
                tables = set(sa.inspect(db.engine).get_table_names())
                self.assertTrue({"users", "documents", "alembic_version"} <= tables)
                db.engine.dispose()

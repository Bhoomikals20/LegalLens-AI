import os

# ===============================
# LegalLens AI Project Generator
# ===============================

folders = [
    "app",
    "app/models",
    "app/routes",
    "app/services",
    "app/services/ai",
    "app/services/ocr",
    "app/services/parser",
    "app/services/rag",
    "app/services/reports",
    "app/services/translator",
    "app/services/notification",
    "app/utils",

    "app/static",
    "app/static/css",
    "app/static/js",
    "app/static/images",
    "app/static/icons",
    "app/static/fonts",

    "app/templates",
    "app/templates/layouts",
    "app/templates/auth",
    "app/templates/dashboard",
    "app/templates/upload",
    "app/templates/analysis",
    "app/templates/chatbot",
    "app/templates/reports",
    "app/templates/translator",
    "app/templates/compare",
    "app/templates/admin",
    "app/templates/settings",
    "app/templates/landing",
    "app/templates/components",

    "database",
    "docs",
    "instance",
    "migrations",
    "tests",
    "uploads",
    "reports",
    "notebooks"
]

files = {

    # Root
    ".env": "",
    ".gitignore": """\
.venv/
__pycache__/
*.pyc
.env
instance/
uploads/
reports/
""",

    "README.md": "# LegalLens AI\n",
    "requirements.txt": "",
    "config.py": "# Configuration will be added later\n",
    "run.py": "# Entry point will be added later\n",

    # App
    "app/__init__.py": "",
    "app/extensions.py": "",

    # Models
    "app/models/__init__.py": "",
    "app/models/user.py": "",
    "app/models/document.py": "",
    "app/models/analysis.py": "",
    "app/models/report.py": "",
    "app/models/chat.py": "",
    "app/models/notification.py": "",

    # Routes
    "app/routes/__init__.py": "",
    "app/routes/auth.py": "",
    "app/routes/dashboard.py": "",
    "app/routes/upload.py": "",
    "app/routes/analysis.py": "",
    "app/routes/chatbot.py": "",
    "app/routes/reports.py": "",
    "app/routes/translator.py": "",
    "app/routes/compare.py": "",
    "app/routes/settings.py": "",
    "app/routes/admin.py": "",
    "app/routes/api.py": "",

    # AI
    "app/services/__init__.py": "",
    "app/services/ai/__init__.py": "",
    "app/services/ai/classifier.py": "",
    "app/services/ai/summarizer.py": "",
    "app/services/ai/simplifier.py": "",
    "app/services/ai/clause_detector.py": "",
    "app/services/ai/missing_clause.py": "",
    "app/services/ai/fairness_meter.py": "",
    "app/services/ai/compliance_checker.py": "",
    "app/services/ai/complexity_meter.py": "",
    "app/services/ai/conflict_detector.py": "",
    "app/services/ai/risk_analysis.py": "",
    "app/services/ai/recommendation.py": "",
    "app/services/ai/timeline.py": "",
    "app/services/ai/deadline.py": "",
    "app/services/ai/legal_dictionary.py": "",
    "app/services/ai/clause_library.py": "",
    "app/services/ai/draft_generator.py": "",
    "app/services/ai/translator_ai.py": "",
    "app/services/ai/voice.py": "",
    "app/services/ai/signature.py": "",
    "app/services/ai/compare_contract.py": "",
    "app/services/ai/heatmap.py": "",

    # OCR
    "app/services/ocr/__init__.py": "",
    "app/services/ocr/easyocr_engine.py": "",
    "app/services/ocr/image_preprocessing.py": "",

    # Parser
    "app/services/parser/__init__.py": "",
    "app/services/parser/pdf_parser.py": "",
    "app/services/parser/docx_parser.py": "",
    "app/services/parser/txt_parser.py": "",
    "app/services/parser/image_parser.py": "",

    # RAG
    "app/services/rag/__init__.py": "",
    "app/services/rag/embeddings.py": "",
    "app/services/rag/vector_store.py": "",
    "app/services/rag/retriever.py": "",
    "app/services/rag/chatbot.py": "",

    # Reports
    "app/services/reports/__init__.py": "",
    "app/services/reports/pdf_report.py": "",
    "app/services/reports/docx_report.py": "",

    # Translator
    "app/services/translator/__init__.py": "",
    "app/services/translator/translate.py": "",

    # Notification
    "app/services/notification/__init__.py": "",
    "app/services/notification/reminder.py": "",

    # Utils
    "app/utils/__init__.py": "",
    "app/utils/constants.py": "",
    "app/utils/helpers.py": "",
    "app/utils/logger.py": "",
    "app/utils/security.py": "",
    "app/utils/validators.py": "",

    # Templates
    "app/templates/layouts/base.html": "<!-- Base Layout -->",
    "app/templates/landing/index.html": "<!-- Landing Page -->",

    # Static
    "app/static/css/style.css": "/* Main Styles */",
    "app/static/js/script.js": "// Main JavaScript",

    # Database
    "database/schema.sql": "-- Database Schema"
}


print("=" * 60)
print("Creating LegalLens AI Project...")
print("=" * 60)

for folder in folders:
    os.makedirs(folder, exist_ok=True)

for file_path, content in files.items():
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

print("\n✅ Project structure created successfully!")
print("Happy Coding 🚀")
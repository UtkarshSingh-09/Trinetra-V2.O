with open("backend/storage/actian_adapter.py", "r") as f:
    text = f.read()

import_str = "from storage.base import StorageClient\nfrom storage.ucso_template import EMPTY_UCSO\nimport requests"

if "requests" not in text:
    text = text.replace("from storage.base import StorageClient", "from storage.base import StorageClient\nimport requests")

init_addition = """
        os.makedirs(self.app_dir, exist_ok=True)
        os.makedirs(self.file_dir, exist_ok=True)
        self.initialize_collections()

    def initialize_collections(self):
        \"\"\"Pre-create all Actian VectorAI collections on backend startup.\"\"\"
        collections = [
            "document_chunks", "financial_profiles", "gst_patterns",
            "bank_recon_profiles", "news_articles", "litigation_records",
            "rbi_circulars", "mca_filings", "pan_profiles", "risk_decisions",
            "pd_transcripts", "stress_scenarios", "audit_events", "application_summaries",
        ]
        url = "http://localhost:5480/api/v1/collections"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer trinetra-local-dev-key"
        }
        for name in collections:
            try:
                requests.post(url, headers=headers, json={"name": name, "dimension": 384, "distance_metric": "cosine"}, timeout=2)
            except Exception:
                pass
"""

text = text.replace("        os.makedirs(self.app_dir, exist_ok=True)\n        os.makedirs(self.file_dir, exist_ok=True)", init_addition)

with open("backend/storage/actian_adapter.py", "w") as f:
    f.write(text)
print("Updated backend/actian_adapter")

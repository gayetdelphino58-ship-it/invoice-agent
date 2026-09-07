"""
Tests unitaires — web/api.py (FastAPI)
Utilise TestClient de Starlette pour tester les endpoints HTTP.
"""

import json
import io
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "web"))

from conftest import SAMPLE_INVOICE, SAMPLE_EXTRACTED

# Import unique de l'app — les patches cibleront web.api.*
from web.api import app

client = TestClient(app, raise_server_exceptions=False)


# ── /api/stats ───────────────────────────────────────────────────

class TestApiStats:

    def test_returns_stats_structure(self):
        invoices_payload = json.dumps({"count": 3, "invoices": [
            {**SAMPLE_INVOICE, "status": "pending"},
            {**SAMPLE_INVOICE, "invoice_id": "id-2", "status": "paid", "amount": "50.00"},
            {**SAMPLE_INVOICE, "invoice_id": "id-3", "status": "overdue", "amount": "30.00"},
        ]})
        reminders_payload = json.dumps({"total_urgent": 1, "invoices": []})

        with patch("web.api.list_invoices", return_value=invoices_payload), \
             patch("web.api.check_due_dates", return_value=reminders_payload):
            resp = client.get("/api/stats")

        assert resp.status_code == 200
        data = resp.json()
        for key in ("total_invoices", "pending", "paid", "overdue", "urgent_count", "total_unpaid"):
            assert key in data

    def test_pending_count_correct(self):
        invoices_payload = json.dumps({"count": 2, "invoices": [
            {**SAMPLE_INVOICE, "status": "pending"},
            {**SAMPLE_INVOICE, "invoice_id": "id-2", "status": "pending", "amount": "20.00"},
        ]})
        with patch("web.api.list_invoices", return_value=invoices_payload), \
             patch("web.api.check_due_dates", return_value=json.dumps({"total_urgent": 0, "invoices": []})):
            resp = client.get("/api/stats")

        assert resp.json()["pending"] == 2


# ── /api/dashboard ───────────────────────────────────────────────

class TestApiDashboard:

    DASHBOARD_PAYLOAD = {
        "month": "2025-07",
        "summary": {"total_amount": 155.49, "invoice_count": 3,
                    "pending": 2, "paid": 1, "overdue": 0, "reminded": 0},
        "by_category": [],
        "top_3_expenses": [],
        "generated_at": "2025-07-01T08:00:00",
    }

    def test_returns_dashboard_data(self):
        with patch("web.api.get_dashboard", return_value=json.dumps(self.DASHBOARD_PAYLOAD)):
            resp = client.get("/api/dashboard?month=2025-07")

        assert resp.status_code == 200
        assert resp.json()["month"] == "2025-07"

    def test_uses_empty_string_when_no_month(self):
        with patch("web.api.get_dashboard", return_value=json.dumps(self.DASHBOARD_PAYLOAD)) as mock_dash:
            client.get("/api/dashboard")

        mock_dash.assert_called_once_with("")

    def test_returns_500_on_error(self):
        with patch("web.api.get_dashboard", return_value=json.dumps({"error": "DynamoDB error"})):
            resp = client.get("/api/dashboard")

        assert resp.status_code == 500


# ── /api/invoices ────────────────────────────────────────────────

class TestApiInvoices:

    def test_list_all_invoices(self):
        payload = json.dumps({"count": 1, "invoices": [SAMPLE_INVOICE]})
        with patch("web.api.list_invoices", return_value=payload):
            resp = client.get("/api/invoices")

        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    def test_filter_by_status_passed_correctly(self):
        payload = json.dumps({"count": 0, "invoices": []})
        with patch("web.api.list_invoices", return_value=payload) as mock_list:
            client.get("/api/invoices?status=paid")

        mock_list.assert_called_with("paid")

    def test_get_invoice_by_id(self):
        with patch("web.api.get_invoice", return_value=json.dumps(SAMPLE_INVOICE)):
            resp = client.get("/api/invoices/test-uuid-1234")

        assert resp.status_code == 200
        assert resp.json()["supplier"] == "EDF"

    def test_get_invoice_not_found_returns_404(self):
        with patch("web.api.get_invoice", return_value=json.dumps({"error": "non trouvée"})):
            resp = client.get("/api/invoices/bad-id")

        assert resp.status_code == 404


# ── /api/reminders ───────────────────────────────────────────────

class TestApiReminders:

    def test_returns_urgent_invoices(self):
        payload = json.dumps({
            "total_urgent": 1, "overdue_count": 0, "upcoming_count": 1,
            "invoices": [{**SAMPLE_INVOICE, "days_left": 2, "priority": "PROCHE"}],
        })
        with patch("web.api.check_due_dates", return_value=payload):
            resp = client.get("/api/reminders")

        assert resp.status_code == 200
        assert resp.json()["total_urgent"] == 1

    def test_send_reminder_success(self):
        ok = json.dumps({"success": True, "supplier": "EDF", "message": "ok", "sns": {}})
        with patch("web.api.send_reminder", return_value=ok):
            resp = client.post("/api/reminders/test-uuid-1234/send")

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_send_reminder_error_returns_500(self):
        with patch("web.api.send_reminder", return_value=json.dumps({"error": "SNS fail"})):
            resp = client.post("/api/reminders/bad-id/send")

        assert resp.status_code == 500


# ── /api/scan ────────────────────────────────────────────────────

class TestApiScan:

    EXTRACTED = json.dumps(SAMPLE_EXTRACTED)
    STORED    = json.dumps({"success": True, "invoice_id": "new-id-abc"})

    def test_scan_pdf_returns_extracted_and_stored(self):
        with patch("web.api.extract_invoice_data", return_value=self.EXTRACTED), \
             patch("web.api.store_invoice", return_value=self.STORED):
            resp = client.post(
                "/api/scan",
                files={"file": ("facture.pdf", io.BytesIO(b"%PDF fake"), "application/pdf")},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["extracted"]["supplier"] == "Orange"
        assert data["stored"]["invoice_id"] == "new-id-abc"

    def test_scan_rejects_unsupported_type(self):
        resp = client.post(
            "/api/scan",
            files={"file": ("invoice.docx", io.BytesIO(b"fake"),
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        assert resp.status_code == 400

    def test_scan_returns_422_on_extraction_error(self):
        with patch("web.api.extract_invoice_data", return_value=json.dumps({"error": "OCR failed"})):
            resp = client.post(
                "/api/scan",
                files={"file": ("facture.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
            )

        assert resp.status_code == 422

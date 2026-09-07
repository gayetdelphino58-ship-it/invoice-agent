"""
Tests unitaires — tools/storage.py
store_invoice, check_due_dates, get_invoice, list_invoices
"""

import json
import pytest
from datetime import date, timedelta
from moto import mock_aws
from unittest.mock import patch

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from conftest import SAMPLE_INVOICE, SAMPLE_EXTRACTED
from tools.storage import store_invoice, check_due_dates, get_invoice, list_invoices


# ── store_invoice ────────────────────────────────────────────────

class TestStoreInvoice:

    def test_stores_valid_invoice_and_returns_id(self, dynamodb_table):
        result = json.loads(store_invoice(json.dumps(SAMPLE_EXTRACTED)))
        assert result["success"] is True
        assert "invoice_id" in result
        assert "Orange" in result["message"]

    def test_rejects_invalid_json(self, dynamodb_table):
        result = json.loads(store_invoice("not valid json {{"))
        assert "error" in result
        assert "JSON invalide" in result["error"]

    def test_rejects_invoice_with_error_field(self, dynamodb_table):
        payload = json.dumps({"error": "Extraction échouée"})
        result = json.loads(store_invoice(payload))
        assert "error" in result

    def test_stored_item_has_pending_status(self, dynamodb_table):
        result = json.loads(store_invoice(json.dumps(SAMPLE_EXTRACTED)))
        invoice_id = result["invoice_id"]
        item = dynamodb_table.get_item(Key={"invoice_id": invoice_id})["Item"]
        assert item["status"] == "pending"
        assert item["supplier"] == "Orange"
        assert item["reminder_sent"] == "false"


# ── check_due_dates ──────────────────────────────────────────────

class TestCheckDueDates:

    def _insert(self, table, overrides):
        item = {**SAMPLE_INVOICE, **overrides}
        table.put_item(Item=item)

    def test_no_pending_invoices_returns_empty(self, dynamodb_table):
        result = json.loads(check_due_dates())
        assert result["total_urgent"] == 0
        assert result["invoices"] == []

    def test_detects_overdue_invoice(self, dynamodb_table):
        past = (date.today() - timedelta(days=5)).isoformat()
        self._insert(dynamodb_table, {"invoice_id": "overdue-1", "due_date": past, "status": "pending"})
        result = json.loads(check_due_dates())
        assert result["overdue_count"] >= 1
        assert "overdue-1" in [i["invoice_id"] for i in result["invoices"]]

    def test_detects_upcoming_invoice_within_3_days(self, dynamodb_table):
        soon = (date.today() + timedelta(days=2)).isoformat()
        self._insert(dynamodb_table, {"invoice_id": "upcoming-1", "due_date": soon, "status": "pending"})
        result = json.loads(check_due_dates())
        assert result["upcoming_count"] >= 1

    def test_ignores_paid_invoices(self, dynamodb_table):
        past = (date.today() - timedelta(days=2)).isoformat()
        self._insert(dynamodb_table, {"invoice_id": "paid-old", "due_date": past, "status": "paid"})
        result = json.loads(check_due_dates())
        assert "paid-old" not in [i["invoice_id"] for i in result["invoices"]]

    def test_ignores_invoice_without_due_date(self, dynamodb_table):
        self._insert(dynamodb_table, {"invoice_id": "no-due-date", "due_date": "", "status": "pending"})
        result = json.loads(check_due_dates())
        assert "no-due-date" not in [i["invoice_id"] for i in result["invoices"]]

    def test_priority_label_for_today(self, dynamodb_table):
        today = date.today().isoformat()
        self._insert(dynamodb_table, {"invoice_id": "today-due", "due_date": today, "status": "pending"})
        result = json.loads(check_due_dates())
        today_inv = next(i for i in result["invoices"] if i["invoice_id"] == "today-due")
        assert today_inv["priority"] == "URGENT"


# ── get_invoice ──────────────────────────────────────────────────

class TestGetInvoice:

    def test_returns_existing_invoice(self, dynamodb_with_data):
        result = json.loads(get_invoice("test-uuid-1234"))
        assert result["invoice_id"] == "test-uuid-1234"
        assert result["supplier"] == "EDF"

    def test_returns_error_for_missing_invoice(self, dynamodb_table):
        result = json.loads(get_invoice("non-existent-id"))
        assert "error" in result
        assert "non trouvée" in result["error"]


# ── list_invoices ────────────────────────────────────────────────

class TestListInvoices:

    def test_lists_all_invoices(self, dynamodb_with_data):
        result = json.loads(list_invoices("all"))
        assert result["count"] >= 1
        assert "test-uuid-1234" in [i["invoice_id"] for i in result["invoices"]]

    def test_filter_by_pending_status(self, dynamodb_with_data):
        result = json.loads(list_invoices("pending"))
        for inv in result["invoices"]:
            assert inv["status"] == "pending"

    def test_filter_by_paid_returns_empty_when_none(self, dynamodb_with_data):
        result = json.loads(list_invoices("paid"))
        assert result["count"] == 0

    def test_sorted_by_due_date(self, dynamodb_table):
        dates = ["2025-08-01", "2025-07-01", "2025-09-01"]
        for i, d in enumerate(dates):
            dynamodb_table.put_item(Item={**SAMPLE_INVOICE, "invoice_id": f"id-{i}", "due_date": d})
        result = json.loads(list_invoices("all"))
        due_dates = [inv["due_date"] for inv in result["invoices"] if inv["due_date"]]
        assert due_dates == sorted(due_dates)

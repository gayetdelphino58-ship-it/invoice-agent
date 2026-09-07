"""
Tests unitaires — tools/dashboard.py
categorize_expense, get_dashboard
"""

import json
import pytest
from datetime import date

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from conftest import SAMPLE_INVOICE
from config import EXPENSE_CATEGORIES
from tools.dashboard import categorize_expense, get_dashboard


def _make_invoice(table, invoice_id, category, amount, due_date, status="pending"):
    table.put_item(Item={
        **SAMPLE_INVOICE,
        "invoice_id": invoice_id,
        "category": category,
        "amount": str(amount),
        "due_date": due_date,
        "status": status,
    })


THIS_MONTH     = date.today().strftime("%Y-%m")
DUE_THIS_MONTH = date.today().replace(day=15).isoformat()


# ── categorize_expense ───────────────────────────────────────────

class TestCategorizeExpense:

    def test_updates_category_successfully(self, dynamodb_with_data):
        result = json.loads(categorize_expense("test-uuid-1234", "Internet"))
        assert result["success"] is True
        assert result["category"] == "Internet"
        item = dynamodb_with_data.get_item(Key={"invoice_id": "test-uuid-1234"})["Item"]
        assert item["category"] == "Internet"

    def test_rejects_invalid_category(self, dynamodb_with_data):
        result = json.loads(categorize_expense("test-uuid-1234", "Loisirs"))
        assert "error" in result
        assert "invalide" in result["error"]

    def test_all_valid_categories_accepted(self, dynamodb_with_data):
        for cat in EXPENSE_CATEGORIES:
            result = json.loads(categorize_expense("test-uuid-1234", cat))
            assert result.get("success") is True, f"Category '{cat}' should be valid"


# ── get_dashboard ────────────────────────────────────────────────

class TestGetDashboard:

    def test_empty_month_returns_zero(self, dynamodb_table):
        result = json.loads(get_dashboard("2099-01"))
        assert result["total"] == 0
        assert "Aucune facture" in result["message"]

    def test_invalid_month_format_returns_error(self, dynamodb_table):
        result = json.loads(get_dashboard("juillet-2025"))
        assert "error" in result

    def test_sums_amounts_correctly(self, dynamodb_table):
        _make_invoice(dynamodb_table, "inv-1", "Electricité", 85.50, DUE_THIS_MONTH)
        _make_invoice(dynamodb_table, "inv-2", "Internet",    49.99, DUE_THIS_MONTH)
        _make_invoice(dynamodb_table, "inv-3", "Eau",         20.00, DUE_THIS_MONTH)
        result = json.loads(get_dashboard(THIS_MONTH))
        assert result["summary"]["total_amount"] == pytest.approx(155.49, rel=1e-3)
        assert result["summary"]["invoice_count"] == 3

    def test_counts_statuses_correctly(self, dynamodb_table):
        _make_invoice(dynamodb_table, "p1", "Loyer",    800.0, DUE_THIS_MONTH, "pending")
        _make_invoice(dynamodb_table, "p2", "Eau",       20.0, DUE_THIS_MONTH, "paid")
        _make_invoice(dynamodb_table, "p3", "Internet",  50.0, DUE_THIS_MONTH, "overdue")
        result = json.loads(get_dashboard(THIS_MONTH))
        s = result["summary"]
        assert s["pending"] == 1
        assert s["paid"]    == 1
        assert s["overdue"] == 1

    def test_by_category_sorted_by_total_desc(self, dynamodb_table):
        _make_invoice(dynamodb_table, "c1", "Internet",    50.0, DUE_THIS_MONTH)
        _make_invoice(dynamodb_table, "c2", "Electricité", 200.0, DUE_THIS_MONTH)
        _make_invoice(dynamodb_table, "c3", "Eau",          30.0, DUE_THIS_MONTH)
        result = json.loads(get_dashboard(THIS_MONTH))
        totals = [c["total"] for c in result["by_category"]]
        assert totals == sorted(totals, reverse=True)

    def test_percentage_sums_to_100(self, dynamodb_table):
        _make_invoice(dynamodb_table, "x1", "Loyer",   600.0, DUE_THIS_MONTH)
        _make_invoice(dynamodb_table, "x2", "Courses", 400.0, DUE_THIS_MONTH)
        result = json.loads(get_dashboard(THIS_MONTH))
        total_pct = sum(c["percentage"] for c in result["by_category"])
        assert total_pct == pytest.approx(100.0, abs=0.5)

    def test_top_3_sorted_by_amount_desc(self, dynamodb_table):
        amounts = [100.0, 500.0, 250.0, 50.0]
        cats    = ["Loyer", "Assurance", "Internet", "Eau"]
        for i, (a, c) in enumerate(zip(amounts, cats)):
            _make_invoice(dynamodb_table, f"t{i}", c, a, DUE_THIS_MONTH)
        result = json.loads(get_dashboard(THIS_MONTH))
        top3 = result["top_3_expenses"]
        assert len(top3) == 3
        assert top3[0]["amount"] == 500.0
        assert top3[1]["amount"] == 250.0
        assert top3[2]["amount"] == 100.0

    def test_default_month_is_current(self, dynamodb_table):
        _make_invoice(dynamodb_table, "now-1", "Téléphone", 30.0, DUE_THIS_MONTH)
        result = json.loads(get_dashboard())
        assert result["month"] == THIS_MONTH
        assert result["summary"]["invoice_count"] >= 1

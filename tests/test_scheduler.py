"""
Tests unitaires — scheduler/lambda_handler.py
"""

import json
import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from conftest import SAMPLE_INVOICE


# ── Helpers ─────────────────────────────────────────────────────

def _urgent(invoice_id, supplier, days_left, priority, reminded=False):
    due = (date.today() + timedelta(days=days_left)).isoformat()
    return {
        "invoice_id": invoice_id,
        "supplier": supplier,
        "amount": "50.00",
        "currency": "EUR",
        "due_date": due,
        "days_left": days_left,
        "priority": priority,
        "reminder_sent": reminded,
    }


def _check_response(invoices):
    return json.dumps({
        "total_urgent": len(invoices),
        "overdue_count": sum(1 for i in invoices if i["days_left"] < 0),
        "upcoming_count": sum(1 for i in invoices if i["days_left"] >= 0),
        "invoices": invoices,
    })


def _send_ok(invoice_id):
    return json.dumps({"success": True, "invoice_id": invoice_id, "supplier": "X", "message": "ok", "sns": {}})


def _send_err(invoice_id):
    return json.dumps({"error": "SNS unavailable"})


# ── Tests ────────────────────────────────────────────────────────

class TestLambdaHandler:

    def test_no_urgent_invoices_returns_zero_sent(self):
        with patch("scheduler.lambda_handler.check_due_dates", return_value=_check_response([])), \
             patch("scheduler.lambda_handler.send_reminder") as mock_send:
            from scheduler.lambda_handler import handler
            result = handler({}, {})

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["reminders_sent"] == 0
        mock_send.assert_not_called()

    def test_sends_reminder_for_each_urgent_invoice(self):
        invoices = [_urgent("id-1", "EDF", -2, "RETARD"), _urgent("id-2", "Orange", 1, "URGENT")]

        with patch("scheduler.lambda_handler.check_due_dates", return_value=_check_response(invoices)), \
             patch("scheduler.lambda_handler.send_reminder", side_effect=[_send_ok("id-1"), _send_ok("id-2")]):
            from scheduler.lambda_handler import handler
            result = handler({}, {})

        body = json.loads(result["body"])
        assert result["statusCode"] == 200
        assert body["reminders_sent"] == 2
        assert body["errors"] == 0

    def test_skips_already_reminded_non_overdue(self):
        invoices = [_urgent("id-remind", "Free", 2, "PROCHE", reminded=True)]

        with patch("scheduler.lambda_handler.check_due_dates", return_value=_check_response(invoices)), \
             patch("scheduler.lambda_handler.send_reminder") as mock_send:
            from scheduler.lambda_handler import handler
            result = handler({}, {})

        body = json.loads(result["body"])
        assert body["skipped"] == 1
        assert body["reminders_sent"] == 0
        mock_send.assert_not_called()

    def test_does_not_skip_overdue_even_if_already_reminded(self):
        invoices = [_urgent("id-late", "GDF", -5, "RETARD", reminded=True)]

        with patch("scheduler.lambda_handler.check_due_dates", return_value=_check_response(invoices)), \
             patch("scheduler.lambda_handler.send_reminder", return_value=_send_ok("id-late")):
            from scheduler.lambda_handler import handler
            result = handler({}, {})

        body = json.loads(result["body"])
        assert body["reminders_sent"] == 1

    def test_handles_sns_error_gracefully(self):
        invoices = [_urgent("id-err", "Bad", 0, "URGENT")]

        with patch("scheduler.lambda_handler.check_due_dates", return_value=_check_response(invoices)), \
             patch("scheduler.lambda_handler.send_reminder", return_value=_send_err("id-err")):
            from scheduler.lambda_handler import handler
            result = handler({}, {})

        body = json.loads(result["body"])
        assert body["errors"] == 1
        assert body["reminders_sent"] == 0
        assert result["statusCode"] == 200   # ne plante pas

    def test_check_due_dates_error_returns_500(self):
        with patch("scheduler.lambda_handler.check_due_dates", return_value=json.dumps({"error": "DynamoDB down"})):
            from scheduler.lambda_handler import handler
            result = handler({}, {})

        assert result["statusCode"] == 500

    def test_check_due_dates_exception_returns_500(self):
        with patch("scheduler.lambda_handler.check_due_dates", side_effect=Exception("Timeout")):
            from scheduler.lambda_handler import handler
            result = handler({}, {})

        assert result["statusCode"] == 500

    def test_body_contains_sent_details(self):
        invoices = [_urgent("id-det", "SFR", 1, "URGENT")]

        with patch("scheduler.lambda_handler.check_due_dates", return_value=_check_response(invoices)), \
             patch("scheduler.lambda_handler.send_reminder", return_value=_send_ok("id-det")):
            from scheduler.lambda_handler import handler
            result = handler({}, {})

        body = json.loads(result["body"])
        assert len(body["sent_details"]) == 1
        assert body["sent_details"][0]["invoice_id"] == "id-det"

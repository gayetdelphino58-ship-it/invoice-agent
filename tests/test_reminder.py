"""
Tests unitaires — tools/reminder.py
"""

import json
import pytest
from datetime import date, timedelta
from unittest.mock import patch

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from conftest import SAMPLE_INVOICE
from tools.reminder import send_reminder, _days_until


class TestSendReminder:

    def test_sends_reminder_and_updates_status(self, dynamodb_with_data, sns_topic):
        result = json.loads(send_reminder("test-uuid-1234"))
        assert result["success"] is True
        assert result["supplier"] == "EDF"
        assert "sns" in result

    def test_updates_dynamodb_status_to_reminded(self, dynamodb_with_data, sns_topic):
        send_reminder("test-uuid-1234")
        item = dynamodb_with_data.get_item(Key={"invoice_id": "test-uuid-1234"})["Item"]
        assert item["status"] == "reminded"
        assert item["reminder_sent"] == "true"
        assert "last_reminder_at" in item

    def test_returns_error_for_missing_invoice(self, dynamodb_table):
        result = json.loads(send_reminder("non-existent-id"))
        assert "error" in result
        assert "introuvable" in result["error"]

    def test_dev_mode_when_no_sns_arn(self, dynamodb_with_data):
        with patch("tools.reminder.SNS_TOPIC_ARN", ""):
            result = json.loads(send_reminder("test-uuid-1234"))
        assert result["success"] is True
        assert result["sns"]["dev_mode"] is True

    def test_overdue_invoice_has_negative_days(self, dynamodb_table):
        past = (date.today() - timedelta(days=10)).isoformat()
        dynamodb_table.put_item(Item={**SAMPLE_INVOICE, "invoice_id": "overdue-test", "due_date": past})
        with patch("tools.reminder.SNS_TOPIC_ARN", ""):
            result = json.loads(send_reminder("overdue-test"))
        assert result["success"] is True


class TestDaysUntil:

    def test_future_date(self):
        future = (date.today() + timedelta(days=5)).isoformat()
        assert _days_until(future) == 5

    def test_past_date(self):
        past = (date.today() - timedelta(days=3)).isoformat()
        assert _days_until(past) == -3

    def test_today(self):
        assert _days_until(date.today().isoformat()) == 0

    def test_invalid_string_returns_none(self):
        assert _days_until("not-a-date") is None

    def test_none_returns_none(self):
        assert _days_until(None) is None

    def test_empty_string_returns_none(self):
        assert _days_until("") is None

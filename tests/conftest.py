"""
Fixtures et mocks AWS partagés pour tous les tests.
Utilise moto (mock AWS) + pytest fixtures.
"""

import json
import os
import pytest
import boto3
from moto import mock_aws
from unittest.mock import MagicMock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import AWS_REGION, DYNAMODB_TABLE_NAME


# ── Constantes de test ───────────────────────────────────────────

SAMPLE_INVOICE = {
    "invoice_id": "test-uuid-1234",
    "supplier": "EDF",
    "amount": "85.50",
    "currency": "EUR",
    "issue_date": "2025-06-01",
    "due_date": "2025-07-15",
    "invoice_number": "FAC-2025-001",
    "category": "Electricité",
    "confidence": "0.95",
    "status": "pending",
    "created_at": "2025-06-01T10:00:00",
    "updated_at": "2025-06-01T10:00:00",
    "reminder_sent": "false",
}

SAMPLE_EXTRACTED = {
    "supplier": "Orange",
    "amount": 49.99,
    "currency": "EUR",
    "issue_date": "2025-07-01",
    "due_date": "2025-07-20",
    "invoice_number": "FAC-ORANGE-777",
    "category": "Téléphone",
    "confidence": 0.92,
    "extracted_at": "2025-07-01T08:00:00",
}


# ── Fixtures pytest ──────────────────────────────────────────────

@pytest.fixture(scope="function", autouse=False)
def aws_credentials():
    """Fournit des credentials AWS factices pour moto."""
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
    os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
    os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
    os.environ.setdefault("AWS_DEFAULT_REGION", AWS_REGION)
    yield


@pytest.fixture(scope="function")
def dynamodb_table(aws_credentials):
    """Crée une table DynamoDB mockée, active pour toute la durée du test."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        table = dynamodb.create_table(
            TableName=DYNAMODB_TABLE_NAME,
            KeySchema=[{"AttributeName": "invoice_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "invoice_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        yield table


@pytest.fixture(scope="function")
def dynamodb_with_data(aws_credentials):
    """Table DynamoDB mockée pré-remplie avec une facture exemple."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        table = dynamodb.create_table(
            TableName=DYNAMODB_TABLE_NAME,
            KeySchema=[{"AttributeName": "invoice_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "invoice_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        table.put_item(Item=SAMPLE_INVOICE)
        yield table


@pytest.fixture(scope="function")
def sns_topic(aws_credentials):
    """Crée un topic SNS mocké et le met dans SNS_TOPIC_ARN."""
    with mock_aws():
        sns = boto3.client("sns", region_name=AWS_REGION)
        response = sns.create_topic(Name="invoice-agent-reminders-test")
        topic_arn = response["TopicArn"]
        os.environ["SNS_TOPIC_ARN"] = topic_arn
        yield topic_arn
    os.environ.pop("SNS_TOPIC_ARN", None)


@pytest.fixture
def mock_bedrock_response():
    """Retourne une factory de réponses Bedrock mockées."""
    def _make(content: dict):
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps({
            "content": [{"text": json.dumps(content)}]
        }).encode()
        return {"body": mock_body}
    return _make


@pytest.fixture
def mock_textract_response():
    """Mock d'une réponse Textract valide."""
    return {
        "Blocks": [
            {"BlockType": "LINE", "Text": "EDF"},
            {"BlockType": "LINE", "Text": "Montant : 85,50 EUR"},
            {"BlockType": "LINE", "Text": "Date d'échéance : 15/07/2025"},
            {"BlockType": "LINE", "Text": "Facture N° FAC-2025-001"},
        ]
    }

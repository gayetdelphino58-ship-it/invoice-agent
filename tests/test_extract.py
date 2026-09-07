"""
Tests unitaires — tools/extract.py
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from moto import mock_aws

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.extract import extract_invoice_data, _parse_with_bedrock, _extract_text_with_textract


# ── _extract_text_with_textract ──────────────────────────────────

class TestExtractTextWithTextract:

    def test_returns_lines_joined(self, mock_textract_response, aws_credentials):
        with mock_aws():
            with patch("tools.extract.boto3.client") as mock_client:
                mock_boto = MagicMock()
                mock_boto.detect_document_text.return_value = mock_textract_response
                mock_client.return_value = mock_boto

                result = _extract_text_with_textract(
                    __import__("pathlib").Path("/fake/invoice.pdf")
                )

        assert "EDF" in result
        assert "85,50 EUR" in result
        assert "15/07/2025" in result

    def test_returns_error_on_exception(self, aws_credentials):
        with patch("tools.extract.boto3.client") as mock_client:
            mock_boto = MagicMock()
            mock_boto.detect_document_text.side_effect = Exception("Textract unavailable")
            mock_client.return_value = mock_boto

            result = _extract_text_with_textract(
                __import__("pathlib").Path("/fake/invoice.pdf")
            )

        assert result.startswith("ERREUR Textract")


# ── _parse_with_bedrock ──────────────────────────────────────────

class TestParseWithBedrock:

    EXPECTED_FIELDS = ["supplier", "amount", "currency", "due_date", "category", "confidence"]

    def test_returns_valid_json_with_all_fields(self, mock_bedrock_response):
        payload = {
            "supplier": "EDF",
            "amount": 85.5,
            "currency": "EUR",
            "issue_date": "2025-06-01",
            "due_date": "2025-07-15",
            "invoice_number": "FAC-001",
            "category": "Electricité",
            "confidence": 0.95,
        }
        with patch("tools.extract.boto3.client") as mock_client:
            mock_boto = MagicMock()
            mock_boto.invoke_model.return_value = mock_bedrock_response(payload)
            mock_client.return_value = mock_boto

            result = json.loads(_parse_with_bedrock("texte de facture EDF"))

        for field in self.EXPECTED_FIELDS:
            assert field in result
        assert result["supplier"] == "EDF"
        assert result["amount"] == 85.5
        assert "extracted_at" in result

    def test_handles_invalid_json_from_claude(self):
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps({
            "content": [{"text": "Ce n'est pas du JSON valide !"}]
        }).encode()

        with patch("tools.extract.boto3.client") as mock_client:
            mock_boto = MagicMock()
            mock_boto.invoke_model.return_value = {"body": mock_body}
            mock_client.return_value = mock_boto

            result = json.loads(_parse_with_bedrock("texte"))

        assert "error" in result

    def test_handles_bedrock_exception(self):
        with patch("tools.extract.boto3.client") as mock_client:
            mock_boto = MagicMock()
            mock_boto.invoke_model.side_effect = Exception("Bedrock timeout")
            mock_client.return_value = mock_boto

            result = json.loads(_parse_with_bedrock("texte"))

        assert "error" in result
        assert "Bedrock" in result["error"]


# ── extract_invoice_data (tool) ──────────────────────────────────

class TestExtractInvoiceTool:

    def test_file_not_found(self):
        result = json.loads(extract_invoice_data("/non/existent/file.pdf"))
        assert "error" in result
        assert "introuvable" in result["error"]

    def test_unsupported_format(self, tmp_path):
        f = tmp_path / "invoice.docx"
        f.write_bytes(b"fake docx content")
        result = json.loads(extract_invoice_data(str(f)))
        assert "error" in result
        assert "non supporté" in result["error"]

    def test_txt_file_calls_bedrock(self, tmp_path, mock_bedrock_response):
        f = tmp_path / "invoice.txt"
        f.write_text("Facture EDF Montant 85.50 EUR Échéance 2025-07-15")

        payload = {
            "supplier": "EDF", "amount": 85.5, "currency": "EUR",
            "issue_date": None, "due_date": "2025-07-15",
            "invoice_number": None, "category": "Electricité", "confidence": 0.9,
        }

        with patch("tools.extract.boto3.client") as mock_client:
            mock_boto = MagicMock()
            mock_boto.invoke_model.return_value = mock_bedrock_response(payload)
            mock_client.return_value = mock_boto

            result = json.loads(extract_invoice_data(str(f)))

        assert result["supplier"] == "EDF"
        assert result["amount"] == 85.5

    def test_pdf_file_calls_textract_then_bedrock(self, tmp_path, mock_bedrock_response, mock_textract_response):
        f = tmp_path / "invoice.pdf"
        f.write_bytes(b"%PDF fake content")

        payload = {
            "supplier": "EDF", "amount": 85.5, "currency": "EUR",
            "issue_date": "2025-06-01", "due_date": "2025-07-15",
            "invoice_number": "FAC-001", "category": "Electricité", "confidence": 0.95,
        }

        with patch("tools.extract.boto3.client") as mock_client:
            mock_textract = MagicMock()
            mock_textract.detect_document_text.return_value = mock_textract_response
            mock_bedrock = MagicMock()
            mock_bedrock.invoke_model.return_value = mock_bedrock_response(payload)

            def client_factory(service, **kwargs):
                return mock_textract if service == "textract" else mock_bedrock

            mock_client.side_effect = client_factory

            result = json.loads(extract_invoice_data(str(f)))

        assert result["supplier"] == "EDF"
        mock_textract.detect_document_text.assert_called_once()
        mock_bedrock.invoke_model.assert_called_once()

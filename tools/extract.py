"""
Tool: extract_invoice_data
Extrait les données structurées d'une facture via AWS Textract + Claude.
Supporte : PDF, PNG, JPG, texte brut.
"""

import json
import base64
import boto3
from pathlib import Path
from datetime import datetime
from strands import tool

from config import AWS_REGION


@tool
def extract_invoice_data(file_path: str) -> str:
    """
    Extrait les informations clés d'une facture à partir d'un fichier.

    Analyse le fichier fourni (PDF, image PNG/JPG, ou texte brut) et extrait :
    - Le nom du fournisseur
    - Le montant total (en euros ou autre devise)
    - La date d'émission
    - La date d'échéance
    - La catégorie de dépense suggérée
    - Un numéro de facture si présent

    Args:
        file_path: Chemin absolu ou relatif vers le fichier de la facture.

    Returns:
        JSON string avec les champs extraits, ou un message d'erreur.
    """
    path = Path(file_path)

    if not path.exists():
        return json.dumps({"error": f"Fichier introuvable : {file_path}"})

    suffix = path.suffix.lower()

    # --- Texte brut : extraction directe ---
    if suffix in (".txt",):
        raw_text = path.read_text(encoding="utf-8")
        return _parse_with_bedrock(raw_text)

    # --- PDF / Image : OCR via AWS Textract ---
    if suffix in (".pdf", ".png", ".jpg", ".jpeg"):
        raw_text = _extract_text_with_textract(path)
        if raw_text.startswith("ERREUR"):
            return json.dumps({"error": raw_text})
        return _parse_with_bedrock(raw_text)

    return json.dumps({"error": f"Format non supporté : {suffix}. Utilisez PDF, PNG, JPG ou TXT."})


def _extract_text_with_textract(path: Path) -> str:
    """Utilise AWS Textract pour extraire le texte d'un PDF ou d'une image."""
    try:
        textract = boto3.client("textract", region_name=AWS_REGION)
        with open(path, "rb") as f:
            file_bytes = f.read()

        response = textract.detect_document_text(
            Document={"Bytes": file_bytes}
        )

        lines = [
            block["Text"]
            for block in response.get("Blocks", [])
            if block["BlockType"] == "LINE"
        ]
        return "\n".join(lines)

    except Exception as e:
        return f"ERREUR Textract : {str(e)}"


def _parse_with_bedrock(raw_text: str) -> str:
    """Envoie le texte brut à Claude via Bedrock pour extraire les champs structurés."""
    try:
        bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)

        prompt = f"""Voici le texte d'une facture. Extrais les informations suivantes et réponds UNIQUEMENT avec un JSON valide, sans aucun texte avant ou après.

Champs attendus :
- supplier: nom du fournisseur (string)
- amount: montant total en nombre décimal (ex: 45.90), null si non trouvé
- currency: devise (ex: "EUR", "USD"), "EUR" par défaut
- issue_date: date d'émission au format YYYY-MM-DD, null si non trouvée
- due_date: date d'échéance au format YYYY-MM-DD, null si non trouvée
- invoice_number: numéro de facture (string), null si non trouvé
- category: catégorie parmi [Electricité, Eau, Internet, Téléphone, Loyer, Assurance, Abonnement, Courses, Santé, Transport, Autre]
- confidence: niveau de confiance global entre 0.0 et 1.0

Texte de la facture :
\"\"\"
{raw_text[:4000]}
\"\"\"

Réponds uniquement avec le JSON :"""

        response = bedrock.invoke_model(
            modelId="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 512,
                "messages": [{"role": "user", "content": prompt}],
            }),
            contentType="application/json",
            accept="application/json",
        )

        body = json.loads(response["body"].read())
        content = body["content"][0]["text"].strip()

        # Valider que c'est bien du JSON
        parsed = json.loads(content)

        # Ajouter timestamp d'extraction
        parsed["extracted_at"] = datetime.utcnow().isoformat()

        return json.dumps(parsed, ensure_ascii=False, indent=2)

    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Réponse Claude non parseable : {str(e)}", "raw": content})
    except Exception as e:
        return json.dumps({"error": f"Erreur Bedrock : {str(e)}"})

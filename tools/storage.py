"""
Tools: store_invoice, check_due_dates, get_invoice, list_invoices
Gestion du stockage et de la surveillance des échéances via DynamoDB.
"""

import json
import uuid
from datetime import datetime, date, timedelta
import boto3
from boto3.dynamodb.conditions import Attr
from strands import tool

from config import AWS_REGION, DYNAMODB_TABLE_NAME, REMINDER_DAYS_BEFORE


def _get_table():
    """Retourne la table DynamoDB (lazy init)."""
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    return dynamodb.Table(DYNAMODB_TABLE_NAME)


# ---------------------------------------------------------------------------
# store_invoice
# ---------------------------------------------------------------------------

@tool
def store_invoice(invoice_json: str) -> str:
    """
    Enregistre une facture extraite dans la base de données DynamoDB.

    Prend le JSON retourné par extract_invoice_data et le persiste.
    Génère un identifiant unique pour chaque facture.
    Retourne l'ID de la facture créée ou un message d'erreur.

    Args:
        invoice_json: JSON string contenant les champs de la facture
                      (supplier, amount, due_date, category, etc.).

    Returns:
        JSON string avec l'invoice_id créé, ou un message d'erreur.
    """
    try:
        data = json.loads(invoice_json)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"JSON invalide : {str(e)}"})

    if "error" in data:
        return json.dumps({"error": f"Impossible d'enregistrer une facture en erreur : {data['error']}"})

    invoice_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    item = {
        "invoice_id": invoice_id,
        "supplier": data.get("supplier", "Inconnu"),
        "amount": str(data.get("amount", "0")),
        "currency": data.get("currency", "EUR"),
        "issue_date": data.get("issue_date") or "",
        "due_date": data.get("due_date") or "",
        "invoice_number": data.get("invoice_number") or "",
        "category": data.get("category", "Autre"),
        "confidence": str(data.get("confidence", 1.0)),
        "status": "pending",          # pending | paid | overdue | reminded
        "created_at": now,
        "updated_at": now,
        "reminder_sent": "false",
    }

    try:
        _get_table().put_item(Item=item)
        return json.dumps({
            "success": True,
            "invoice_id": invoice_id,
            "message": f"Facture '{item['supplier']}' ({item['amount']} {item['currency']}) enregistrée avec succès. ID : {invoice_id}",
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Erreur DynamoDB : {str(e)}"})


# ---------------------------------------------------------------------------
# check_due_dates
# ---------------------------------------------------------------------------

@tool
def check_due_dates() -> str:
    """
    Vérifie toutes les factures en attente et identifie celles dont l'échéance approche.

    Retourne la liste des factures nécessitant un rappel :
    - Échéance dans moins de REMINDER_DAYS_BEFORE jours (défaut : 3 jours)
    - Ou déjà en retard (date d'échéance dépassée)

    Ne modifie pas la base de données — utilise send_reminder pour envoyer les alertes.

    Returns:
        JSON string avec la liste des factures urgentes classées par priorité.
    """
    try:
        table = _get_table()
        response = table.scan(
            FilterExpression=Attr("status").eq("pending")
        )
        items = response.get("Items", [])
    except Exception as e:
        return json.dumps({"error": f"Erreur DynamoDB scan : {str(e)}"})

    today = date.today()
    threshold = today + timedelta(days=REMINDER_DAYS_BEFORE)

    overdue = []
    upcoming = []

    for item in items:
        due_str = item.get("due_date", "")
        if not due_str:
            continue
        try:
            due = date.fromisoformat(due_str)
        except ValueError:
            continue

        days_left = (due - today).days

        entry = {
            "invoice_id": item["invoice_id"],
            "supplier": item["supplier"],
            "amount": item["amount"],
            "currency": item["currency"],
            "due_date": due_str,
            "days_left": days_left,
            "reminder_sent": item.get("reminder_sent", "false") == "true",
        }

        if days_left < 0:
            entry["priority"] = "RETARD"
            overdue.append(entry)
        elif due <= threshold:
            entry["priority"] = "URGENT" if days_left <= 1 else "PROCHE"
            upcoming.append(entry)

    # Trier par urgence
    overdue.sort(key=lambda x: x["days_left"])
    upcoming.sort(key=lambda x: x["days_left"])

    all_urgent = overdue + upcoming

    return json.dumps({
        "total_urgent": len(all_urgent),
        "overdue_count": len(overdue),
        "upcoming_count": len(upcoming),
        "invoices": all_urgent,
    }, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# get_invoice
# ---------------------------------------------------------------------------

@tool
def get_invoice(invoice_id: str) -> str:
    """
    Récupère les détails complets d'une facture par son ID.

    Args:
        invoice_id: L'identifiant unique de la facture (UUID).

    Returns:
        JSON string avec tous les champs de la facture, ou une erreur si non trouvée.
    """
    try:
        table = _get_table()
        response = table.get_item(Key={"invoice_id": invoice_id})
        item = response.get("Item")
        if not item:
            return json.dumps({"error": f"Facture non trouvée : {invoice_id}"})
        return json.dumps(item, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Erreur DynamoDB : {str(e)}"})


# ---------------------------------------------------------------------------
# list_invoices
# ---------------------------------------------------------------------------

@tool
def list_invoices(status: str = "all") -> str:
    """
    Liste toutes les factures enregistrées, avec filtre optionnel par statut.

    Args:
        status: Filtre par statut — "all" (défaut), "pending", "paid", "overdue", "reminded".

    Returns:
        JSON string avec la liste des factures triées par date d'échéance.
    """
    try:
        table = _get_table()
        if status == "all":
            response = table.scan()
        else:
            response = table.scan(FilterExpression=Attr("status").eq(status))

        items = response.get("Items", [])
        items.sort(key=lambda x: x.get("due_date", "9999-99-99"))

        return json.dumps({
            "count": len(items),
            "invoices": items,
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Erreur DynamoDB : {str(e)}"})

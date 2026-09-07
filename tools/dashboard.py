"""
Tools: categorize_expense, get_dashboard
Catégorisation des dépenses et tableau de bord mensuel.
"""

import json
from datetime import datetime, date
from collections import defaultdict
import boto3
from boto3.dynamodb.conditions import Attr
from strands import tool

from config import AWS_REGION, DYNAMODB_TABLE_NAME, EXPENSE_CATEGORIES


def _get_table():
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    return dynamodb.Table(DYNAMODB_TABLE_NAME)


# ---------------------------------------------------------------------------
# categorize_expense
# ---------------------------------------------------------------------------

@tool
def categorize_expense(invoice_id: str, category: str) -> str:
    """
    Met à jour manuellement la catégorie d'une facture existante.

    Permet de corriger la catégorie assignée automatiquement lors de l'extraction.

    Args:
        invoice_id: L'identifiant unique de la facture.
        category: La nouvelle catégorie parmi : Electricité, Eau, Internet,
                  Téléphone, Loyer, Assurance, Abonnement, Courses, Santé,
                  Transport, Autre.

    Returns:
        JSON string confirmant la mise à jour ou indiquant l'erreur.
    """
    if category not in EXPENSE_CATEGORIES:
        return json.dumps({
            "error": f"Catégorie '{category}' invalide. Choisissez parmi : {', '.join(EXPENSE_CATEGORIES)}"
        })

    try:
        table = _get_table()
        now = datetime.utcnow().isoformat()
        table.update_item(
            Key={"invoice_id": invoice_id},
            UpdateExpression="SET category = :c, updated_at = :u",
            ExpressionAttributeValues={":c": category, ":u": now},
        )
        return json.dumps({
            "success": True,
            "invoice_id": invoice_id,
            "category": category,
            "message": f"Catégorie mise à jour → {category}",
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Erreur DynamoDB : {str(e)}"})


# ---------------------------------------------------------------------------
# get_dashboard
# ---------------------------------------------------------------------------

@tool
def get_dashboard(month: str = "") -> str:
    """
    Génère un tableau de bord complet des dépenses pour un mois donné.

    Affiche :
    - Total des dépenses du mois
    - Répartition par catégorie (montant + pourcentage)
    - Nombre de factures payées / en attente / en retard
    - Les 3 dépenses les plus élevées
    - Comparaison avec le mois précédent si disponible

    Args:
        month: Mois au format "YYYY-MM" (ex: "2025-07"). Par défaut : mois en cours.

    Returns:
        JSON string avec le résumé complet du mois.
    """
    if not month:
        month = date.today().strftime("%Y-%m")

    # Valider le format
    try:
        year, mon = month.split("-")
        year, mon = int(year), int(mon)
    except (ValueError, AttributeError):
        return json.dumps({"error": f"Format de mois invalide : '{month}'. Utilisez YYYY-MM."})

    try:
        table = _get_table()
        # Scanner toutes les factures du mois (issue_date ou due_date commençant par YYYY-MM)
        response = table.scan()
        all_items = response.get("Items", [])
    except Exception as e:
        return json.dumps({"error": f"Erreur DynamoDB : {str(e)}"})

    # Filtrer les factures du mois cible (sur due_date)
    month_items = [
        item for item in all_items
        if item.get("due_date", "").startswith(month)
    ]

    if not month_items:
        return json.dumps({
            "month": month,
            "message": f"Aucune facture trouvée pour {month}.",
            "total": 0,
        })

    # --- Calculs ---
    total = 0.0
    by_category = defaultdict(float)
    by_status = defaultdict(int)
    top_expenses = []

    for item in month_items:
        try:
            amount = float(item.get("amount", 0))
        except (ValueError, TypeError):
            amount = 0.0

        category = item.get("category", "Autre")
        status = item.get("status", "pending")

        total += amount
        by_category[category] += amount
        by_status[status] += 1

        top_expenses.append({
            "supplier": item.get("supplier", "?"),
            "amount": amount,
            "category": category,
            "due_date": item.get("due_date", ""),
        })

    # Top 3 dépenses
    top_expenses.sort(key=lambda x: x["amount"], reverse=True)
    top_3 = top_expenses[:3]

    # Répartition catégories avec pourcentage
    categories_breakdown = []
    for cat in EXPENSE_CATEGORIES:
        if cat in by_category:
            cat_total = by_category[cat]
            categories_breakdown.append({
                "category": cat,
                "total": round(cat_total, 2),
                "percentage": round((cat_total / total * 100) if total > 0 else 0, 1),
                "count": sum(1 for i in month_items if i.get("category") == cat),
            })
    categories_breakdown.sort(key=lambda x: x["total"], reverse=True)

    dashboard = {
        "month": month,
        "summary": {
            "total_amount": round(total, 2),
            "currency": "EUR",
            "invoice_count": len(month_items),
            "pending": by_status.get("pending", 0),
            "paid": by_status.get("paid", 0),
            "overdue": by_status.get("overdue", 0),
            "reminded": by_status.get("reminded", 0),
        },
        "by_category": categories_breakdown,
        "top_3_expenses": top_3,
        "generated_at": datetime.utcnow().isoformat(),
    }

    return json.dumps(dashboard, ensure_ascii=False, indent=2)

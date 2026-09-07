"""
Tool: send_reminder
Envoie des rappels de paiement via AWS SNS et met à jour le statut en DynamoDB.
"""

import json
from datetime import datetime
import boto3
from strands import tool

from config import AWS_REGION, DYNAMODB_TABLE_NAME, SNS_TOPIC_ARN


def _get_table():
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    return dynamodb.Table(DYNAMODB_TABLE_NAME)


@tool
def send_reminder(invoice_id: str) -> str:
    """
    Envoie un rappel de paiement pour une facture donnée via AWS SNS.

    Compose un message clair avec les détails de la facture (fournisseur,
    montant, date d'échéance, jours restants) et l'envoie sur le topic SNS
    configuré (email, SMS selon l'abonnement SNS).

    Met à jour le statut de la facture à "reminded" et enregistre la date d'envoi.

    Args:
        invoice_id: L'identifiant unique de la facture à rappeler.

    Returns:
        JSON string confirmant l'envoi ou indiquant l'erreur.
    """
    # --- Récupérer la facture ---
    try:
        table = _get_table()
        response = table.get_item(Key={"invoice_id": invoice_id})
        item = response.get("Item")
    except Exception as e:
        return json.dumps({"error": f"Erreur DynamoDB get : {str(e)}"})

    if not item:
        return json.dumps({"error": f"Facture introuvable : {invoice_id}"})

    # --- Construire le message ---
    supplier = item.get("supplier", "Fournisseur inconnu")
    amount = item.get("amount", "?")
    currency = item.get("currency", "EUR")
    due_date = item.get("due_date", "?")
    invoice_number = item.get("invoice_number", "")
    days_left = _days_until(due_date)

    if days_left is None:
        urgency_line = "⚠️  Date d'échéance non renseignée."
    elif days_left < 0:
        urgency_line = f"🔴 EN RETARD de {abs(days_left)} jour(s) !"
    elif days_left == 0:
        urgency_line = "🔴 ÉCHÉANCE AUJOURD'HUI !"
    elif days_left == 1:
        urgency_line = "🟠 Échéance DEMAIN !"
    else:
        urgency_line = f"🟡 Échéance dans {days_left} jour(s)."

    ref_line = f"Réf. facture : {invoice_number}\n" if invoice_number else ""

    message = f"""📋 RAPPEL DE PAIEMENT — Invoice Agent

Fournisseur : {supplier}
Montant     : {amount} {currency}
Échéance    : {due_date}
{ref_line}
{urgency_line}

→ Pensez à effectuer votre paiement avant la date limite.

—
Invoice Agent (AWS Strands) • {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC
"""

    subject = f"[Invoice Agent] Rappel : {supplier} — {amount} {currency} dû le {due_date}"

    # --- Envoyer via SNS ---
    if not SNS_TOPIC_ARN:
        # Mode développement : afficher dans la console
        print("\n" + "=" * 50)
        print("📬 [DEV MODE] Rappel qui aurait été envoyé :")
        print(message)
        print("=" * 50)
        sns_result = {"dev_mode": True, "message_printed": True}
    else:
        try:
            sns = boto3.client("sns", region_name=AWS_REGION)
            sns_response = sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=subject,
                Message=message,
            )
            sns_result = {"message_id": sns_response["MessageId"]}
        except Exception as e:
            return json.dumps({"error": f"Erreur SNS publish : {str(e)}"})

    # --- Mettre à jour le statut DynamoDB ---
    try:
        now = datetime.utcnow().isoformat()
        table.update_item(
            Key={"invoice_id": invoice_id},
            UpdateExpression="SET #s = :s, reminder_sent = :r, last_reminder_at = :t, updated_at = :u",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": "reminded",
                ":r": "true",
                ":t": now,
                ":u": now,
            },
        )
    except Exception as e:
        return json.dumps({"error": f"Rappel envoyé mais erreur mise à jour DynamoDB : {str(e)}"})

    return json.dumps({
        "success": True,
        "invoice_id": invoice_id,
        "supplier": supplier,
        "message": f"Rappel envoyé pour '{supplier}' ({amount} {currency}), échéance {due_date}.",
        "sns": sns_result,
    }, ensure_ascii=False)


def _days_until(due_date_str: str):
    """Calcule le nombre de jours jusqu'à l'échéance (négatif si retard)."""
    try:
        from datetime import date
        due = date.fromisoformat(due_date_str)
        return (due - date.today()).days
    except (ValueError, TypeError):
        return None

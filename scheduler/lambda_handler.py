"""
Lambda Handler — Scheduler automatique des rappels de factures.
Déclenché chaque matin à 8h00 par AWS EventBridge.

Ce handler :
1. Appelle check_due_dates() pour trouver les factures urgentes
2. Envoie un rappel SNS pour chacune (si pas déjà envoyé)
3. Retourne un résumé de l'exécution dans les logs CloudWatch
"""

import json
import logging
import sys
import os

# Ajouter le dossier parent au path pour importer les tools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.storage import check_due_dates
from tools.reminder import send_reminder

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Point d'entrée Lambda — déclenché par EventBridge (cron).
    """
    logger.info("⏰ Invoice Agent Scheduler démarré")

    # --- 1. Vérifier les échéances ---
    try:
        due_result = json.loads(check_due_dates())
    except Exception as e:
        logger.error(f"Erreur check_due_dates : {e}")
        return _response(500, {"error": str(e)})

    if "error" in due_result:
        logger.error(f"Erreur retournée par check_due_dates : {due_result['error']}")
        return _response(500, due_result)

    urgent_invoices = due_result.get("invoices", [])
    total_urgent = due_result.get("total_urgent", 0)

    logger.info(f"📋 {total_urgent} facture(s) urgente(s) trouvée(s)")

    if total_urgent == 0:
        logger.info("✅ Aucun rappel nécessaire aujourd'hui.")
        return _response(200, {
            "message": "Aucun rappel nécessaire.",
            "reminders_sent": 0,
        })

    # --- 2. Envoyer les rappels ---
    sent = []
    skipped = []
    errors = []

    for invoice in urgent_invoices:
        invoice_id = invoice["invoice_id"]
        already_reminded = invoice.get("reminder_sent", False)

        if already_reminded and invoice.get("priority") != "RETARD":
            # Ne pas re-notifier sauf si vraiment en retard
            skipped.append(invoice_id)
            logger.info(f"⏭️  Rappel déjà envoyé pour {invoice_id}, ignoré.")
            continue

        try:
            result = json.loads(send_reminder(invoice_id))
            if result.get("success"):
                sent.append({
                    "invoice_id": invoice_id,
                    "supplier": invoice.get("supplier"),
                    "due_date": invoice.get("due_date"),
                    "priority": invoice.get("priority"),
                })
                logger.info(
                    f"📬 Rappel envoyé — {invoice.get('supplier')} "
                    f"({invoice.get('amount')} {invoice.get('currency')}) "
                    f"échéance {invoice.get('due_date')} [{invoice.get('priority')}]"
                )
            else:
                errors.append({"invoice_id": invoice_id, "error": result.get("error")})
                logger.warning(f"⚠️  Échec rappel {invoice_id} : {result.get('error')}")
        except Exception as e:
            errors.append({"invoice_id": invoice_id, "error": str(e)})
            logger.error(f"❌ Exception rappel {invoice_id} : {e}")

    summary = {
        "total_urgent": total_urgent,
        "reminders_sent": len(sent),
        "skipped": len(skipped),
        "errors": len(errors),
        "sent_details": sent,
        "error_details": errors,
    }

    logger.info(f"✅ Scheduler terminé : {len(sent)} rappel(s) envoyé(s), {len(errors)} erreur(s)")
    return _response(200, summary)


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "body": json.dumps(body, ensure_ascii=False),
    }

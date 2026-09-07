"""
AgentCore Runtime — Point d'entrée pour le déploiement sur Amazon Bedrock AgentCore.
Expose l'Invoice Agent comme un service HTTP prêt pour AgentCore.
"""

import json
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Compatibilité AgentCore : le working directory peut varier
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from strands import Agent
from strands.models import BedrockModel
from amazon_bedrock_agentcore.runtime import AgentCoreApp

from config import AWS_REGION, BEDROCK_MODEL_ID
from tools import (
    extract_invoice_data,
    store_invoice,
    check_due_dates,
    get_invoice,
    list_invoices,
    send_reminder,
    categorize_expense,
    get_dashboard,
)

# ------------------------------------------------------------------ #
# Prompt système                                                       #
# ------------------------------------------------------------------ #
SYSTEM_PROMPT = """
Tu es un assistant de gestion de factures intelligent et proactif.

Tes responsabilités :
1. Extraire les données des factures (PDF, image, texte).
2. Stocker chaque facture en base de données.
3. Vérifier les échéances et envoyer des rappels automatiques avant retard.
4. Catégoriser les dépenses et fournir un tableau de bord mensuel.
5. N'impliquer l'utilisateur QUE pour les décisions humaines réelles.

Réponds toujours en français. Sois concis et factuel.
"""

# ------------------------------------------------------------------ #
# Création de l'agent Strands                                          #
# ------------------------------------------------------------------ #
model = BedrockModel(
    model_id=BEDROCK_MODEL_ID,
    region_name=AWS_REGION,
)

agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[
        extract_invoice_data,
        store_invoice,
        check_due_dates,
        get_invoice,
        list_invoices,
        send_reminder,
        categorize_expense,
        get_dashboard,
    ],
)

# ------------------------------------------------------------------ #
# AgentCore App                                                        #
# ------------------------------------------------------------------ #
app = AgentCoreApp()


@app.entrypoint
def invoke(payload: dict, context) -> dict:
    """
    Point d'entrée AgentCore.
    Reçoit un payload JSON avec un champ 'message' et retourne la réponse de l'agent.
    """
    message = payload.get("message", "")
    session_id = payload.get("session_id", "default")

    if not message:
        return {"error": "Champ 'message' manquant dans le payload."}

    try:
        response = agent(message)
        return {
            "session_id": session_id,
            "response": str(response),
            "status": "success",
        }
    except Exception as e:
        return {
            "session_id": session_id,
            "error": str(e),
            "status": "error",
        }


if __name__ == "__main__":
    app.run()

"""
Invoice Agent — Agent principal Strands
Gère automatiquement vos factures : extraction, stockage, rappels, dashboard.
"""

import sys
from strands import Agent
from strands.models import BedrockModel

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

SYSTEM_PROMPT = """
Tu es un assistant de gestion de factures intelligent et proactif.

Tes responsabilités principales :
1. EXTRAIRE les informations clés des factures (PDF, image, texte brut) :
   - Fournisseur, montant, date d'émission, date d'échéance, catégorie.

2. STOCKER chaque facture extraite dans la base de données.

3. VÉRIFIER régulièrement les dates d'échéance et envoyer des rappels
   automatiques AVANT qu'une facture soit en retard.

4. CATÉGORISER les dépenses et fournir un tableau de bord mensuel clair.

5. N'impliquer l'utilisateur QUE lorsqu'une décision humaine est vraiment nécessaire
   (ex. : montant anormalement élevé, fournisseur inconnu, paiement litigieux).

Principes :
- Tu travailles en arrière-plan et silencieusement autant que possible.
- Sois précis, concis et factuel dans tes résumés.
- En cas de doute sur une information d'une facture, indique-le clairement.
- Toujours répondre en français.
"""


def create_agent() -> Agent:
    """Crée et configure l'agent Strands avec tous ses outils."""
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
    return agent


def main():
    """Point d'entrée principal — mode interactif en ligne de commande."""
    agent = create_agent()

    print("=" * 60)
    print("🧾  Invoice Agent — Gestionnaire de factures automatique")
    print("=" * 60)
    print("Commandes rapides :")
    print("  • 'scan <chemin>'       → Analyser une facture (PDF/image)")
    print("  • 'rappels'             → Vérifier les échéances proches")
    print("  • 'dashboard'           → Voir le résumé des dépenses")
    print("  • 'liste'               → Lister toutes les factures")
    print("  • 'quitter'             → Quitter l'agent")
    print("-" * 60)

    while True:
        try:
            user_input = input("\nVous > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Agent arrêté.")
            sys.exit(0)

        if not user_input:
            continue

        if user_input.lower() in ("quitter", "exit", "quit"):
            print("👋 Agent arrêté.")
            break

        # Raccourcis clavier → instructions naturelles pour l'agent
        shortcuts = {
            "rappels": "Vérifie toutes les factures et envoie les rappels nécessaires pour celles dont l'échéance approche.",
            "dashboard": "Génère le tableau de bord complet des dépenses du mois en cours.",
            "liste": "Liste toutes les factures enregistrées avec leur statut.",
        }

        if user_input.lower() in shortcuts:
            message = shortcuts[user_input.lower()]
        elif user_input.lower().startswith("scan "):
            path = user_input[5:].strip()
            message = f"Extrais et enregistre la facture depuis ce fichier : {path}"
        else:
            message = user_input

        print("\nAgent 🤖 ...")
        response = agent(message)
        print(f"\nAgent > {response}")


if __name__ == "__main__":
    main()

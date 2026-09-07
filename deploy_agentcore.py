#!/usr/bin/env python3
"""
Script de déploiement AgentCore — Invoice Agent
Déploie l'agent sur Amazon Bedrock AgentCore via la CLI officielle.

Usage :
    python deploy_agentcore.py                    # déploiement complet
    python deploy_agentcore.py --status           # vérifier le statut
    python deploy_agentcore.py --invoke "message" # tester en production
"""

import argparse
import json
import subprocess
import sys
import os


AGENT_NAME = "invoice-agent"
ENTRYPOINT_FILE = "agentcore_app.py"


def run(cmd: list[str], check=True) -> subprocess.CompletedProcess:
    """Exécute une commande shell et affiche la sortie."""
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False, text=True, check=check)
    return result


def deploy():
    """Déploiement complet : bootstrap + création/mise à jour de l'agent."""
    print("\n🚀 Déploiement Invoice Agent sur AgentCore\n")
    print("─" * 50)

    # 1. Bootstrap AgentCore (première fois uniquement)
    print("\n[1/4] Bootstrap AgentCore...")
    run(["agentcore", "bootstrap"], check=False)

    # 2. Initialiser le projet AgentCore si pas encore fait
    agentcore_yaml = os.path.join(os.path.dirname(__file__), "agentcore.yaml")
    if not os.path.exists(agentcore_yaml):
        print("\n[2/4] Initialisation du projet AgentCore...")
        run([
            "agentcore", "init",
            "--name", AGENT_NAME,
            "--entrypoint", ENTRYPOINT_FILE,
        ])
    else:
        print("\n[2/4] Projet AgentCore déjà initialisé.")

    # 3. Build de l'image Docker
    print("\n[3/4] Build de l'image Docker...")
    run(["agentcore", "build"])

    # 4. Déploiement sur AgentCore
    print("\n[4/4] Déploiement sur AgentCore...")
    run(["agentcore", "deploy"])

    print("\n✅ Déploiement terminé !")
    print("   → Vérifiez le statut avec : python deploy_agentcore.py --status")


def status():
    """Vérifie le statut du déploiement AgentCore."""
    print("\n📊 Statut AgentCore Invoice Agent\n")
    run(["agentcore", "status"])


def invoke_agent(message: str):
    """Envoie un message à l'agent déployé sur AgentCore."""
    print(f"\n📨 Invocation AgentCore : '{message}'\n")
    payload = json.dumps({"message": message})
    run([
        "agentcore", "invoke",
        "--payload", payload,
    ])


def main():
    parser = argparse.ArgumentParser(description="Déploiement AgentCore — Invoice Agent")
    parser.add_argument("--status", action="store_true", help="Vérifier le statut du déploiement")
    parser.add_argument("--invoke", type=str, metavar="MESSAGE", help="Tester l'agent en production")
    args = parser.parse_args()

    if args.status:
        status()
    elif args.invoke:
        invoke_agent(args.invoke)
    else:
        deploy()


if __name__ == "__main__":
    main()

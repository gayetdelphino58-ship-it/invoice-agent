# 🧾 Invoice Agent — Gestionnaire de Factures Automatique

Agent IA construit avec le **SDK Strands Agents** (AWS) pour gérer vos factures automatiquement.
Soumis au hackathon **Agents for Humans** — catégorie *Agents du quotidien*.

---

## 🎯 Ce que fait l'agent

| Capacité | Détail |
|---|---|
| 📥 **Extraction** | Lit vos factures (PDF, image, texte) via AWS Textract + Claude |
| 💾 **Stockage** | Enregistre chaque facture dans DynamoDB |
| ⏰ **Rappels** | Envoie une alerte automatique avant l'échéance (via SNS) |
| 📊 **Dashboard** | Résumé mensuel des dépenses par catégorie |
| 🔄 **Surveillance** | Détecte les factures en retard ou urgentes |

L'agent fonctionne **en arrière-plan** et ne vous sollicite que si une vraie décision humaine est nécessaire.

---

## 🏗️ Architecture

```
invoice-agent/
├── agent.py              # Agent principal Strands (CLI interactive)
├── agentcore_app.py      # Point d'entrée AgentCore (production)
├── deploy_agentcore.py   # Script de déploiement AgentCore
├── config.py             # Configuration centralisée
├── setup_aws.py          # Script de création des ressources AWS
├── requirements.txt      # Toutes les dépendances Python
├── Dockerfile            # Image Docker pour AgentCore
├── cdk.json              # Config AWS CDK
├── .env.example
├── tools/
│   ├── extract.py        # AWS Textract + Claude → JSON structuré
│   ├── storage.py        # DynamoDB : store, list, check_due_dates
│   ├── reminder.py       # AWS SNS : envoi de rappels
│   └── dashboard.py      # Tableau de bord mensuel
├── scheduler/
│   └── lambda_handler.py # Lambda EventBridge (rappels auto 8h/jour)
└── infra/
    ├── app.py            # AWS CDK : déploiement infra complète
    └── requirements.txt  # Dépendances CDK
```

**Services AWS utilisés :**
- **Amazon Bedrock** (Claude 3.5 Sonnet) — intelligence de l'agent
- **AWS Textract** — OCR des PDFs et images
- **Amazon DynamoDB** — stockage des factures
- **Amazon SNS** — notifications de rappels
- **AWS Lambda + EventBridge** — scheduler quotidien automatique (8h00)
- **AgentCore** — déploiement et hébergement en production

---

## 🚀 Installation & Lancement

### 1. Prérequis

```bash
python 3.11+
pip install -r requirements.txt
```

### 2. Configuration AWS

```bash
cp .env.example .env
# Remplir AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
```

### 3. Créer les ressources AWS

```bash
python setup_aws.py
```

Ce script crée automatiquement :
- La table DynamoDB `invoices`
- Le topic SNS `invoice-agent-reminders`

### 4. Abonner votre email aux rappels

```bash
aws sns subscribe \
  --topic-arn <ARN_AFFICHÉ_PAR_SETUP> \
  --protocol email \
  --notification-endpoint votre@email.com
```

### 5. Lancer l'agent (mode local)

```bash
python agent.py
```

---

## ☁️ Déploiement Production (AgentCore)

### 1. Déployer l'infra AWS (CDK)

```bash
pip install -r infra/requirements.txt
cdk deploy -c account=VOTRE_COMPTE_AWS -c email=votre@email.com
```

### 2. Déployer l'agent sur AgentCore

```bash
pip install amazon-bedrock-agentcore
python deploy_agentcore.py
```

### 3. Vérifier le statut

```bash
python deploy_agentcore.py --status
```

### 4. Tester en production

```bash
python deploy_agentcore.py --invoke "Vérifie les factures urgentes"
```

---

## ⏰ Scheduler Automatique (EventBridge)

Le scheduler Lambda [`scheduler/lambda_handler.py`](scheduler/lambda_handler.py) est déclenché **chaque matin à 8h00 UTC (lundi–vendredi)** par EventBridge.

Il :
1. Scanne toutes les factures `pending` dont l'échéance approche (≤ 3 jours)
2. Envoie automatiquement les rappels SNS
3. Logue l'exécution dans CloudWatch

Aucune action manuelle requise une fois l'infra déployée.

---

## 💬 Utilisation

```
Vous > scan /chemin/vers/facture.pdf
Vous > rappels
Vous > dashboard
Vous > liste
Vous > Marque la facture abc-123 comme payée
```

---

## ⚙️ Variables d'environnement

| Variable | Description | Défaut |
|---|---|---|
| `AWS_REGION` | Région AWS | `us-east-1` |
| `BEDROCK_MODEL_ID` | Modèle Claude | `claude-3-5-sonnet` |
| `DYNAMODB_TABLE_NAME` | Nom de la table | `invoices` |
| `SNS_TOPIC_ARN` | ARN du topic SNS | *(dev: console)* |
| `REMINDER_DAYS_BEFORE` | Jours avant rappel | `3` |

---

## 🛠️ Outils (Tools) Strands

| Tool | Rôle |
|---|---|
| `extract_invoice_data` | Extrait les données d'un fichier facture |
| `store_invoice` | Enregistre en DynamoDB |
| `check_due_dates` | Identifie les factures urgentes |
| `get_invoice` | Récupère une facture par ID |
| `list_invoices` | Liste toutes les factures |
| `send_reminder` | Envoie un rappel SNS |
| `categorize_expense` | Corrige la catégorie d'une facture |
| `get_dashboard` | Génère le tableau de bord mensuel |

---

*Construit avec ❤️ pour le hackathon AWS **Agents for Humans***

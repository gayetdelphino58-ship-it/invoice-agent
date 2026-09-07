# Invoice Agent — Tests

Ce dossier contient l'ensemble des tests unitaires du projet.

## Structure

```
tests/
├── conftest.py          ← Fixtures partagées (mocks AWS, données exemple)
├── test_extract.py      ← Tests tools/extract.py  (Textract + Bedrock)
├── test_storage.py      ← Tests tools/storage.py  (DynamoDB CRUD)
├── test_reminder.py     ← Tests tools/reminder.py (SNS + statuts)
├── test_dashboard.py    ← Tests tools/dashboard.py (calculs + dashboard)
├── test_api.py          ← Tests web/api.py         (endpoints FastAPI)
└── test_scheduler.py    ← Tests scheduler/lambda_handler.py
```

## Lancer les tests

```bash
# Installer les dépendances de test
pip install -r requirements.txt

# Tous les tests
pytest

# Avec couverture de code
pytest --cov --cov-report=term-missing

# Un fichier spécifique
pytest tests/test_storage.py -v

# Une classe spécifique
pytest tests/test_storage.py::TestCheckDueDates -v

# Un test spécifique
pytest tests/test_storage.py::TestCheckDueDates::test_detects_overdue_invoice -v
```

## Technologies utilisées

| Outil | Usage |
|---|---|
| **pytest** | Framework de test |
| **moto** | Mock AWS (DynamoDB, SNS, Textract) |
| **FastAPI TestClient** | Tests HTTP des endpoints API |
| **unittest.mock** | Mock de Bedrock et autres dépendances |
| **pytest-cov** | Couverture de code (seuil : 80%) |

## Couverture cible

| Module | Couverture cible |
|---|---|
| `tools/extract.py` | ≥ 80% |
| `tools/storage.py` | ≥ 90% |
| `tools/reminder.py` | ≥ 85% |
| `tools/dashboard.py` | ≥ 85% |
| `web/api.py` | ≥ 80% |
| `scheduler/lambda_handler.py` | ≥ 90% |

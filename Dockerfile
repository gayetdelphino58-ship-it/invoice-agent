FROM python:3.12-slim

WORKDIR /app

# Installer les dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code source
COPY . .

# Port AgentCore
EXPOSE 8080

# Point d'entrée AgentCore
CMD ["python", "agentcore_app.py"]

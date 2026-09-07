"""
API FastAPI — Invoice Agent Web Interface
Expose les données DynamoDB via des endpoints REST consommés par le frontend.
"""

import json
import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

# Ajouter le dossier parent au path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.storage import check_due_dates, list_invoices, get_invoice
from tools.dashboard import get_dashboard
from tools.reminder import send_reminder
from tools.extract import extract_invoice_data
from tools.storage import store_invoice

app = FastAPI(
    title="Invoice Agent API",
    description="API REST pour le gestionnaire de factures automatique",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir les fichiers statiques du frontend
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ------------------------------------------------------------------ #
# Routes frontend                                                      #
# ------------------------------------------------------------------ #

@app.get("/", response_class=FileResponse)
def serve_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


# ------------------------------------------------------------------ #
# API — Dashboard                                                      #
# ------------------------------------------------------------------ #

@app.get("/api/dashboard")
def api_dashboard(month: Optional[str] = None):
    """Retourne le tableau de bord mensuel."""
    result = json.loads(get_dashboard(month or ""))
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


# ------------------------------------------------------------------ #
# API — Factures                                                       #
# ------------------------------------------------------------------ #

@app.get("/api/invoices")
def api_list_invoices(status: str = "all"):
    """Liste toutes les factures avec filtre optionnel par statut."""
    result = json.loads(list_invoices(status))
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@app.get("/api/invoices/{invoice_id}")
def api_get_invoice(invoice_id: str):
    """Retourne les détails d'une facture par son ID."""
    result = json.loads(get_invoice(invoice_id))
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.patch("/api/invoices/{invoice_id}/status")
def api_update_status(invoice_id: str, status: str):
    """Met à jour le statut d'une facture (paid, pending, overdue)."""
    import boto3
    from config import AWS_REGION, DYNAMODB_TABLE_NAME
    allowed = {"pending", "paid", "overdue", "reminded"}
    if status not in allowed:
        raise HTTPException(status_code=400, detail=f"Statut invalide. Valeurs: {allowed}")
    try:
        dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        table = dynamodb.Table(DYNAMODB_TABLE_NAME)
        table.update_item(
            Key={"invoice_id": invoice_id},
            UpdateExpression="SET #s = :s, updated_at = :u",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": status,
                ":u": datetime.utcnow().isoformat(),
            },
        )
        return {"success": True, "invoice_id": invoice_id, "status": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------ #
# API — Rappels                                                        #
# ------------------------------------------------------------------ #

@app.get("/api/reminders")
def api_check_reminders():
    """Retourne les factures urgentes nécessitant un rappel."""
    result = json.loads(check_due_dates())
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@app.post("/api/reminders/{invoice_id}/send")
def api_send_reminder(invoice_id: str):
    """Envoie manuellement un rappel pour une facture."""
    result = json.loads(send_reminder(invoice_id))
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


# ------------------------------------------------------------------ #
# API — Scan / Upload                                                  #
# ------------------------------------------------------------------ #

@app.post("/api/scan")
async def api_scan_invoice(file: UploadFile = File(...)):
    """
    Upload et analyse une facture (PDF, PNG, JPG, TXT).
    Retourne les données extraites ET enregistre la facture en base.
    """
    # Vérifier le type de fichier
    allowed_types = {"application/pdf", "image/png", "image/jpeg", "text/plain"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Type de fichier non supporté : {file.content_type}",
        )

    # Sauvegarder temporairement le fichier
    import tempfile
    suffix = os.path.splitext(file.filename or "invoice.pdf")[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        # Extraire les données
        extracted = json.loads(extract_invoice_data(tmp_path))
        if "error" in extracted:
            raise HTTPException(status_code=422, detail=extracted["error"])

        # Stocker la facture
        stored = json.loads(store_invoice(json.dumps(extracted)))
        if "error" in stored:
            raise HTTPException(status_code=500, detail=stored["error"])

        return {
            "extracted": extracted,
            "stored": stored,
        }
    finally:
        os.unlink(tmp_path)


# ------------------------------------------------------------------ #
# API — Stats rapides                                                  #
# ------------------------------------------------------------------ #

@app.get("/api/stats")
def api_stats():
    """Retourne les statistiques globales pour le header du dashboard."""
    all_invoices = json.loads(list_invoices("all"))
    reminders = json.loads(check_due_dates())

    invoices = all_invoices.get("invoices", [])
    total_amount = sum(
        float(i.get("amount", 0))
        for i in invoices
        if i.get("status") != "paid"
    )

    return {
        "total_invoices": all_invoices.get("count", 0),
        "pending": sum(1 for i in invoices if i.get("status") == "pending"),
        "paid": sum(1 for i in invoices if i.get("status") == "paid"),
        "overdue": sum(1 for i in invoices if i.get("status") == "overdue"),
        "urgent_count": reminders.get("total_urgent", 0),
        "total_unpaid": round(total_amount, 2),
    }


# ------------------------------------------------------------------ #
# Lancement                                                            #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)

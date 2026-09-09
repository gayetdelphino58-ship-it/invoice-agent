"""
API FastAPI — Mode démonstration (sans AWS)
Utilise des données fictives pour la démo Railway.
"""

import json
import os
from datetime import datetime, date
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

app = FastAPI(title="Invoice Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ── Données de démo (dates relatives à aujourd'hui) ─────────────
def _rel(days: int) -> str:
    """Retourne une date ISO relative à aujourd'hui (±jours)."""
    from datetime import timedelta
    return (date.today() + timedelta(days=days)).isoformat()

def _month(delta_months: int) -> str:
    """Retourne le 1er jour du mois +delta_months."""
    from datetime import timedelta
    d = date.today()
    month = (d.month - 1 + delta_months) % 12 + 1
    year  = d.year + ((d.month - 1 + delta_months) // 12)
    return date(year, month, 1).isoformat()

DEMO_INVOICES = [
    {"invoice_id": "inv-001", "supplier": "EDF", "amount": "85.50", "currency": "EUR",
     "issue_date": _rel(-30), "due_date": _rel(15), "invoice_number": "FAC-2025-001",
     "category": "Electricité", "status": "pending", "reminder_sent": "false"},
    {"invoice_id": "inv-002", "supplier": "Orange", "amount": "49.99", "currency": "EUR",
     "issue_date": _rel(-15), "due_date": _rel(20), "invoice_number": "FAC-ORANGE-777",
     "category": "Téléphone", "status": "pending", "reminder_sent": "false"},
    {"invoice_id": "inv-003", "supplier": "Loyer Appartement", "amount": "800.00", "currency": "EUR",
     "issue_date": _rel(-20), "due_date": _rel(-1), "invoice_number": f"LOYER-{date.today().strftime('%m-%Y')}",
     "category": "Loyer", "status": "paid", "reminder_sent": "true"},
    {"invoice_id": "inv-004", "supplier": "Société Générale Eau", "amount": "32.40", "currency": "EUR",
     "issue_date": _rel(-45), "due_date": _rel(-5), "invoice_number": "EAU-2025-456",
     "category": "Eau", "status": "overdue", "reminder_sent": "true"},
    {"invoice_id": "inv-005", "supplier": "Netflix", "amount": "17.99", "currency": "EUR",
     "issue_date": _rel(-10), "due_date": _rel(10), "invoice_number": f"NF-{date.today().strftime('%Y%m%d')}",
     "category": "Abonnement", "status": "pending", "reminder_sent": "false"},
    {"invoice_id": "inv-006", "supplier": "AXA Assurance", "amount": "120.00", "currency": "EUR",
     "issue_date": _rel(-20), "due_date": _rel(25), "invoice_number": "AXA-2025-789",
     "category": "Assurance", "status": "reminded", "reminder_sent": "true"},
]


@app.get("/", response_class=FileResponse)
def serve_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/stats")
def api_stats():
    total_unpaid = sum(float(i["amount"]) for i in DEMO_INVOICES if i["status"] != "paid")
    return {
        "total_invoices": len(DEMO_INVOICES),
        "pending":  sum(1 for i in DEMO_INVOICES if i["status"] == "pending"),
        "paid":     sum(1 for i in DEMO_INVOICES if i["status"] == "paid"),
        "overdue":  sum(1 for i in DEMO_INVOICES if i["status"] == "overdue"),
        "urgent_count": sum(1 for i in DEMO_INVOICES if i["status"] in ("pending", "overdue")),
        "total_unpaid": round(total_unpaid, 2),
    }


@app.get("/api/dashboard")
def api_dashboard(month: Optional[str] = None):
    if not month:
        month = date.today().strftime("%Y-%m")
    items = [i for i in DEMO_INVOICES if i.get("due_date", "").startswith(month)]
    if not items:
        items = DEMO_INVOICES  # afficher toutes les données en démo
    total = sum(float(i["amount"]) for i in items)
    by_cat = {}
    for i in items:
        cat = i["category"]
        by_cat[cat] = by_cat.get(cat, 0) + float(i["amount"])
    categories = sorted(
        [{"category": k, "total": round(v, 2), "percentage": round(v / total * 100, 1) if total else 0}
         for k, v in by_cat.items()],
        key=lambda x: x["total"], reverse=True
    )
    top3 = sorted(items, key=lambda x: float(x["amount"]), reverse=True)[:3]
    return {
        "month": month,
        "summary": {
            "total_amount": round(total, 2), "currency": "EUR",
            "invoice_count": len(items),
            "pending":  sum(1 for i in items if i["status"] == "pending"),
            "paid":     sum(1 for i in items if i["status"] == "paid"),
            "overdue":  sum(1 for i in items if i["status"] == "overdue"),
            "reminded": sum(1 for i in items if i["status"] == "reminded"),
        },
        "by_category": categories,
        "top_3_expenses": [{"supplier": i["supplier"], "amount": float(i["amount"]), "category": i["category"]} for i in top3],
        "generated_at": datetime.utcnow().isoformat(),
    }


@app.get("/api/invoices")
def api_list_invoices(status: str = "all"):
    items = DEMO_INVOICES if status == "all" else [i for i in DEMO_INVOICES if i["status"] == status]
    return {"count": len(items), "invoices": sorted(items, key=lambda x: x.get("due_date", ""))}


@app.get("/api/invoices/{invoice_id}")
def api_get_invoice(invoice_id: str):
    item = next((i for i in DEMO_INVOICES if i["invoice_id"] == invoice_id), None)
    if not item:
        raise HTTPException(status_code=404, detail=f"Facture non trouvée : {invoice_id}")
    return item


@app.patch("/api/invoices/{invoice_id}/status")
def api_update_status(invoice_id: str, status: str):
    item = next((i for i in DEMO_INVOICES if i["invoice_id"] == invoice_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Facture non trouvée")
    item["status"] = status
    return {"success": True, "invoice_id": invoice_id, "status": status}


@app.get("/api/reminders")
def api_check_reminders():
    urgent = [i for i in DEMO_INVOICES if i["status"] in ("pending", "overdue")]
    return {
        "total_urgent": len(urgent),
        "overdue_count": sum(1 for i in urgent if i["status"] == "overdue"),
        "upcoming_count": sum(1 for i in urgent if i["status"] == "pending"),
        "invoices": [
            {**i, "days_left": -5 if i["status"] == "overdue" else 3,
             "priority": "RETARD" if i["status"] == "overdue" else "PROCHE"}
            for i in urgent
        ],
    }


@app.post("/api/reminders/{invoice_id}/send")
def api_send_reminder(invoice_id: str):
    item = next((i for i in DEMO_INVOICES if i["invoice_id"] == invoice_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Facture non trouvée")
    item["status"] = "reminded"
    item["reminder_sent"] = "true"
    return {"success": True, "invoice_id": invoice_id, "supplier": item["supplier"],
            "message": f"Rappel envoyé pour {item['supplier']}", "sns": {"dev_mode": True}}


@app.post("/api/scan")
async def api_scan_invoice(file: UploadFile = File(...)):
    allowed = {"application/pdf", "image/png", "image/jpeg", "text/plain"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail=f"Type non supporté : {file.content_type}")
    # Démo : retourner des données simulées
    demo_result = {
        "supplier": "Fournisseur Exemple",
        "amount": 75.00, "currency": "EUR",
        "issue_date": date.today().isoformat(),
        "due_date": date.today().replace(day=28).isoformat(),
        "invoice_number": f"DEMO-{date.today().strftime('%Y%m%d')}",
        "category": "Autre", "confidence": 0.88,
        "extracted_at": datetime.utcnow().isoformat(),
    }
    new_id = f"inv-demo-{len(DEMO_INVOICES)+1:03d}"
    DEMO_INVOICES.append({
        "invoice_id": new_id, **{k: str(v) if not isinstance(v, str) else v for k, v in demo_result.items()},
        "status": "pending", "reminder_sent": "false",
    })
    return {"extracted": demo_result, "stored": {"success": True, "invoice_id": new_id,
            "message": f"Facture '{demo_result['supplier']}' enregistrée (mode démo)"}}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("api_demo:app", host="0.0.0.0", port=port, reload=False)

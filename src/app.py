"""
FastAPI app - lead intake form + API endpoint
"""
import logging
from pathlib import Path
from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from .lead_intake import validate_lead, ValidatedLead
from .classify import classify_lead
from .crm_client import process_lead_to_crm
from .notify import get_notifier
from .config import BASE_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CRM Lead Automation",
    description="AI-powered lead qualification + HubSpot integration",
    version="1.0.0"
)

# Templates
templates_dir = BASE_DIR / "templates"
templates_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))

# Static
static_dir = BASE_DIR / "static"
static_dir.mkdir(exist_ok=True)

# Mount static if exists
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health():
    return {"status": "ok", "service": "crm-lead-automation"}

@app.post("/api/lead", response_class=JSONResponse)
async def api_lead(
    name: str = Form(...),
    email: str = Form(...),
    message: str = Form(...),
    phone: str = Form(None),
    source: str = Form("web_form")
):
    """
    Form endpoint - receives lead from HTML form
    """
    try:
        # 1. Validate
        lead_data = {
            "name": name,
            "email": email,
            "message": message,
            "phone": phone,
            "source": source
        }
        lead = validate_lead(lead_data)
        logger.info(f"Validated lead: {lead.email}")

        # 2. Classify
        classification = classify_lead(lead.name, lead.email, lead.message)
        logger.info(f"Classification: {classification.intent} / {classification.priority}, should_create={classification.should_create_deal}")

        # 3. CRM (with deduplication)
        crm_result = process_lead_to_crm(lead, classification)
        logger.info(f"CRM result: contact={crm_result.get('contact', {}).get('id')}, deal_created={crm_result.get('deal_created')}")

        # 4. Notify manager
        notifier = get_notifier()
        notifier.notify_new_lead(lead, classification, crm_result)

        return {
            "status": "success",
            "lead_id": lead.lead_id,
            "classification": classification.model_dump(),
            "crm": {
                "contact_id": crm_result.get("contact", {}).get("id"),
                "deal_id": crm_result.get("deal", {}).get("id") if crm_result.get("deal") else None,
                "deal_created": crm_result.get("deal_created", False),
                "mock": crm_result.get("mock", False)
            },
            "message": "Lead processed successfully" if classification.should_create_deal else "Lead filtered (spam/not a lead) - no deal created"
        }

    except ValidationError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=e.errors())
    except Exception as e:
        logger.exception(f"Lead processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/lead/json", response_class=JSONResponse)
async def api_lead_json(payload: dict):
    """
    JSON endpoint for API integrations
    """
    try:
        lead = validate_lead(payload)
        classification = classify_lead(lead.name, lead.email, lead.message)
        crm_result = process_lead_to_crm(lead, classification)
        notifier = get_notifier()
        notifier.notify_new_lead(lead, classification, crm_result)

        return {
            "status": "success",
            "lead_id": lead.lead_id,
            "classification": classification.model_dump(),
            "crm": crm_result
        }
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())
    except Exception as e:
        logger.exception(f"JSON lead failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# For local dev
if __name__ == "__main__":
    import uvicorn
    from .config import APP_HOST, APP_PORT
    uvicorn.run("src.app:app", host=APP_HOST, port=APP_PORT, reload=True)

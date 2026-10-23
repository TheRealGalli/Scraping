import logging
import secrets
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from config import settings
from services.time_filter import is_night_time, is_sender_operating_hours, get_rome_time
from services.worker import run_lead_generation_task

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("lead_gen_app")

app = FastAPI(
    title="Serverless Lead Generation & Sender API",
    description="GCP Cloud Run Worker service for scraping, lead generation, and cold emailing",
    version="1.0.0"
)

def _is_unauthorized(request: Request) -> bool:
    """Verifies CRON_SECRET header (X-Cron-Secret) or query parameter (?key=... or ?secret=...) if CRON_SECRET is configured."""
    if not settings.CRON_SECRET:
        return False
    header_secret = request.headers.get("X-Cron-Secret")
    query_secret = request.query_params.get("key") or request.query_params.get("secret")
    return header_secret != settings.CRON_SECRET and query_secret != settings.CRON_SECRET

@app.get("/", tags=["Health"])
@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint for Cloud Run container status."""
    now_rome = get_rome_time().strftime("%Y-%m-%d %H:%M:%S %Z")
    return {
        "status": "healthy",
        "service": "Lead Generation & Sender Worker",
        "current_time_rome": now_rome,
        "is_night_time": is_night_time(),
        "is_sender_operating_hours": is_sender_operating_hours()
    }

@app.api_route("/worker", methods=["GET", "POST"], tags=["Worker"])
def trigger_worker(request: Request):
    """
    Cloud Scheduler Invocation Endpoint (/worker).
    
    1. Validates CRON_SECRET header (X-Cron-Secret) or query parameter if CRON_SECRET is set.
    2. Checks Italy (Europe/Rome) time.
    3. If between 22:00 and 06:00 (Anti-Night filter), returns 200 OK immediately without API usage.
    4. Otherwise, executes lead generation task synchronously so Cloud Run keeps CPU active until finished.
    """
    if _is_unauthorized(request):
        logger.warning("[/worker] Unauthorized request: Invalid or missing X-Cron-Secret.")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"status": "error", "message": "Unauthorized: Invalid or missing CRON_SECRET"}
        )

    now_rome = get_rome_time()
    formatted_time = now_rome.strftime("%Y-%m-%d %H:%M:%S %Z")

    # Anti-night filter check
    if is_night_time(now_rome):
        logger.info(f"[/worker] Anti-night filter activated at {formatted_time}. Skipping execution.")
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "skipped",
                "reason": "Anti-night filter active (22:00-06:00 Europe/Rome)",
                "timestamp": formatted_time
            }
        )

    # Execute task synchronously during request to prevent Cloud Run CPU throttling
    logger.info(f"[/worker] Daytime execution triggered at {formatted_time}. Running worker task...")
    run_lead_generation_task()

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "completed",
            "message": "Lead generation worker task executed successfully",
            "timestamp": formatted_time
        }
    )

@app.api_route("/send-emails", methods=["GET", "POST"], tags=["Sender"])
def trigger_email_sender(request: Request):
    """Legacy route intentionally cannot send, including after a Scheduler retry."""
    # Retire the legacy sender: old Scheduler retries must never bypass the registry.
    return {"status": "skipped", "reason": "legacy_sender_retired", "message": "Use POST /send-emails/{campaign_id} after migration"}


@app.post("/send-emails/{campaign_id}", tags=["Sender"])
def trigger_campaign(campaign_id: str, request: Request):
    from services.campaign_catalog import CATALOG
    if campaign_id not in CATALOG:
        return JSONResponse(status_code=404, content={"status": "error", "reason": "unknown_campaign"})
    if not settings.SENDER_CRON_SECRET or not secrets.compare_digest(request.headers.get("X-Sender-Secret", ""), settings.SENDER_CRON_SECRET):
        return JSONResponse(status_code=401, content={"status": "error", "reason": "sender_secret_required"})
    if not settings.SENDING_ENABLED:
        return {"status": "skipped", "reason": "sending_disabled"}
    try:
        from services.campaign_engine import CampaignEngine
        from services.campaign_store import FirestoreStore
        return CampaignEngine(FirestoreStore()).run(campaign_id, request.headers.get("X-CloudScheduler-ScheduleTime", ""))
    except Exception:
        logger.exception("Campaign execution failed; no automatic resend of unresolved dispatches")
        return JSONResponse(status_code=503, content={"status": "error", "reason": "campaign_execution_failed"})

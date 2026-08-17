import logging
from fastapi import FastAPI, BackgroundTasks, status
from fastapi.responses import JSONResponse

from services.time_filter import is_night_time, is_sender_operating_hours, get_rome_time
from services.worker import run_lead_generation_task
from services.sender_worker import run_email_sender_task

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
def trigger_worker(background_tasks: BackgroundTasks):
    """
    Cloud Scheduler Invocation Endpoint (/worker).
    
    1. Checks Italy (Europe/Rome) time.
    2. If between 22:00 and 06:00 (Anti-Night filter), returns 200 OK immediately without API usage.
    3. Otherwise, delegates scraper task execution to BackgroundTasks and responds 200 OK immediately.
    """
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

    # Dispatch background task for lead generation
    logger.info(f"[/worker] Daytime execution triggered at {formatted_time}. Launching worker task in background.")
    background_tasks.add_task(run_lead_generation_task)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "processing",
            "message": "Lead generation background worker started successfully",
            "timestamp": formatted_time
        }
    )

@app.api_route("/send-emails", methods=["GET", "POST"], tags=["Sender"])
def trigger_email_sender(background_tasks: BackgroundTasks):
    """
    Cloud Scheduler Invocation Endpoint (/send-emails).
    
    1. Checks Italy (Europe/Rome) daytime operating hours (06:00 - 22:00).
    2. If outside window, returns 200 OK immediately without SMTP calls.
    3. Otherwise, delegates email sender task execution to BackgroundTasks and responds 200 OK immediately.
    """
    now_rome = get_rome_time()
    formatted_time = now_rome.strftime("%Y-%m-%d %H:%M:%S %Z")

    if not is_sender_operating_hours(now_rome):
        logger.info(f"[/send-emails] Outside operating hours at {formatted_time}. Skipping execution.")
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "skipped",
                "reason": "Outside sender operating hours (06:00-22:00 Europe/Rome)",
                "timestamp": formatted_time
            }
        )

    logger.info(f"[/send-emails] Daytime sender triggered at {formatted_time}. Launching email sender task in background.")
    background_tasks.add_task(run_email_sender_task)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "processing",
            "message": "Email sender background worker started successfully",
            "timestamp": formatted_time
        }
    )

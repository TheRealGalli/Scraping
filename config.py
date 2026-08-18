from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Google Sheet Configuration
    SPREADSHEET_ID: str = "1Efim8M0IGMQ2jv2M57VJEUoRcGSAgci8rxOSBMZpcMY"
    SHEET_NAME: str = "Italy"

    # API Credentials & Vertex AI Configuration
    GOOGLE_API_KEY: str = ""
    CUSTOM_SEARCH_ENGINE_ID: str = ""
    GCP_PROJECT: str = ""
    GCP_PROJECT_ID: str = ""
    CP_PROJECT_ID: str = ""
    GCP_LOCATION: str = "europe-west1"
    GEMINI_MODEL_NAME: str = "gemini-3.5-flash-lite"  # Target model gemini-3.5-flash-lite
    ENABLE_GEMINI_GROUNDING: bool = True  # Enable Vertex AI Google Search Grounding for direct email search

    @property
    def project_id(self) -> str:
        return self.GCP_PROJECT or self.GCP_PROJECT_ID or self.CP_PROJECT_ID or "scraping-505816"

    # Workspace SMTP & Sender Configuration
    WORKSPACE_EMAIL: str = ""
    WORKSPACE_APP_PASSWORD: str = ""
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    MAX_DAILY_EMAILS: int = 50
    EMAILS_PER_BATCH: int = 1            # Send 1 email per Cloud Scheduler invocation
    SEND_DELAY_MIN_SEC: float = 30.0    # Optional delay range
    SEND_DELAY_MAX_SEC: float = 90.0

    # Scraping & Time Filter Settings
    TIMEZONE: str = "Europe/Rome"
    NIGHT_START_HOUR: int = 22  # 22:00
    NIGHT_END_HOUR: int = 6     # 06:00
    HTTP_TIMEOUT: float = 4.0   # seconds per page fetch
    MAX_PLACES_PER_RUN: int = 20
    SLEEP_BETWEEN_CALLS: float = 0.5  # seconds delay for rate limiting

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

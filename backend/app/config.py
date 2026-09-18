from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://clinic:clinic_dev_password@db:5432/clinic"
    jwt_secret: str = "change-me"
    jwt_expire_minutes: int = 720
    automation_key: str = "change-me-automation-key"
    n8n_webhook_url: str = "http://n8n:5678/webhook/clinic-email"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

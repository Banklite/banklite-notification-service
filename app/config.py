from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "notification-service"
    api_port: int = 8007

    database_url: str = "postgresql+psycopg2://banklite:banklite@notification-db:5432/notification_db"

    identity_service_url: str = "http://identity-service:8001"
    identity_timeout_seconds: float = 5.0

    # Correo por Resend (https://resend.com): HTTP, funciona en planes gratis donde SMTP esta bloqueado.
    # Sin RESEND_API_KEY solo se guardan las notificaciones dentro de la app.
    resend_api_key: str | None = None
    email_from: str = "BankLite <onboarding@resend.dev>"


settings = Settings()

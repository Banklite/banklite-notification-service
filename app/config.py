from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "notification-service"
    api_port: int = 8007

    database_url: str = "postgresql+psycopg2://banklite:banklite@notification-db:5432/notification_db"

    identity_service_url: str = "http://identity-service:8001"
    identity_timeout_seconds: float = 5.0

    # Correo por Resend (https://resend.com): HTTP
    resend_api_key: str | None = None
    email_from: str = "BankLite <onboarding@resend.dev>"

    # Correo por Gmail SMTP (smtp.gmail.com:587 con contraseña de aplicación)
    gmail_user: str | None = None
    gmail_app_password: str | None = None
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_use_tls: bool = True

    # WhatsApp Business Cloud API (Meta)
    whatsapp_token: str | None = None
    whatsapp_phone_id: str | None = None
    whatsapp_api_version: str = "v21.0"

    # WhatsApp via CallMeBot
    callmebot_phone: str | None = None
    callmebot_apikey: str | None = None

    # WhatsApp via Green API (Instancia gratuita vinculada por QR como WhatsApp Web)
    greenapi_instance_id: str | None = None
    greenapi_api_token: str | None = None

    # Modo sandbox: si no hay credenciales de terceros, simula el despacho y loguea
    email_sandbox_enabled: bool = True
    whatsapp_sandbox_enabled: bool = True



settings = Settings()

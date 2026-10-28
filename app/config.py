from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "notification-service"
    api_port: int = 8007

    database_url: str = "postgresql+psycopg2://banklite:banklite@notification-db:5432/notification_db"

    identity_service_url: str = "http://identity-service:8001"
    account_service_url: str = "http://account-service:8002"

    # Bus de eventos (RabbitMQ). Apagado por defecto: se activa con ENABLE_CONSUMER=true.
    rabbitmq_url: str = "amqp://banklite:banklite@rabbitmq:5672/"
    events_exchange: str = "banklite.events"
    events_queue: str = "notification.events"
    enable_consumer: bool = False
    identity_timeout_seconds: float = 5.0

    # Correo por Resend (https://resend.com): HTTP
    resend_api_key: str | None = None
    email_from: str = "BankLite <onboarding@resend.dev>"

    # Correo por Brevo (https://brevo.com): HTTP, funciona en Render gratis (que bloquea SMTP).
    # BREVO_SENDER_EMAIL debe ser un remitente verificado en la cuenta de Brevo.
    brevo_api_key: str | None = None
    brevo_sender_email: str | None = None
    brevo_sender_name: str = "BankLite"

    # Correo por Gmail SMTP (smtp.gmail.com:587 con contraseña de aplicación).
    # OJO: los web services gratuitos de Render bloquean los puertos SMTP.
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

    # Modo sandbox (solo desarrollo): registra el mensaje en el log pero NO lo envia
    # y lo reporta como NO entregado. Apagado por defecto: un envio fallido se
    # informa como fallido, nunca como exitoso.
    email_sandbox_enabled: bool = False
    whatsapp_sandbox_enabled: bool = False



settings = Settings()

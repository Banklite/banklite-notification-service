"""Modulo de envio de correos electronicos (Multi-proveedor: Gmail SMTP, Resend HTTP, Sandbox)."""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from .config import settings

logger = logging.getLogger(__name__)


def get_user_email(id_usuario) -> str | None:
    try:
        r = httpx.get(
            f"{settings.identity_service_url}/users/{id_usuario}",
            timeout=settings.identity_timeout_seconds,
        )
        if r.status_code == 200:
            return r.json().get("email")
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo consultar identity-service: %s", exc)
    return None


def _build_html_template(subject: str, message: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; }}
        .card {{ max-width: 520px; margin: 0 auto; background: #ffffff; border-radius: 16px; padding: 32px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }}
        .header {{ border-bottom: 2px solid #f1f5f9; padding-bottom: 16px; margin-bottom: 24px; }}
        .logo {{ color: #26474E; font-size: 24px; font-weight: 800; letter-spacing: -0.5px; margin: 0; }}
        .badge {{ display: inline-block; background: #E0F2F1; color: #00897B; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 700; margin-top: 4px; }}
        .title {{ color: #0f172a; font-size: 18px; font-weight: 700; margin-top: 0; }}
        .content {{ color: #334155; font-size: 15px; line-height: 1.6; white-space: pre-line; }}
        .footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid #f1f5f9; color: #94a3b8; font-size: 12px; line-height: 1.4; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="header">
          <h1 class="logo">BankLite</h1>
          <span class="badge">BANCA DIGITAL SEGURA</span>
        </div>
        <h2 class="title">{subject}</h2>
        <div class="content">{message}</div>
        <div class="footer">
          <p>Este es un correo automatico generado por BankLite Core Banking. Por tu seguridad, nunca compartas tus claves o codigos de seguridad con nadie.</p>
        </div>
      </div>
    </body>
    </html>
    """


def send_email_via_gmail(to: str, subject: str, text: str, html: str | None = None) -> bool:
    """Envia correo autenticado usando Gmail SMTP (smtp.gmail.com:587 con contraseña de aplicacion)."""
    if not settings.gmail_user or not settings.gmail_app_password:
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"BankLite <{settings.gmail_user}>"
    msg["To"] = to

    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html or _build_html_template(subject, text), "html", "utf-8"))

    try:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
        if settings.smtp_use_tls:
            server.starttls()
        server.login(settings.gmail_user, settings.gmail_app_password)
        server.sendmail(settings.gmail_user, [to], msg.as_string())
        server.quit()
        logger.info("[GMAIL-SMTP] Correo enviado exitosamente a %s: '%s'", to, subject)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("[GMAIL-SMTP] Error al enviar correo a %s: %s", to, exc)
        return False


def send_email_via_resend(to: str, subject: str, text: str, html: str | None = None) -> bool:
    """Envia correo usando la API REST HTTP de Resend."""
    if not settings.resend_api_key:
        return False

    body_html = html or _build_html_template(subject, text)
    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={"from": settings.email_from, "to": [to], "subject": subject, "html": body_html},
            timeout=10.0,
        )
        if r.status_code >= 400:
            logger.warning("[RESEND-API] Error %s: %s", r.status_code, r.text[:200])
            return False
        logger.info("[RESEND-API] Correo enviado a %s: '%s'", to, subject)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("[RESEND-API] Fallo HTTP: %s", exc)
        return False


def send_email_via_brevo(to: str, subject: str, text: str, html: str | None = None) -> bool:
    """Envia correo usando la API REST HTTP de Brevo (sirve en Render gratis)."""
    if not settings.brevo_api_key or not settings.brevo_sender_email:
        return False

    try:
        r = httpx.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": settings.brevo_api_key, "accept": "application/json"},
            json={
                "sender": {"name": settings.brevo_sender_name, "email": settings.brevo_sender_email},
                "to": [{"email": to}],
                "subject": subject,
                "htmlContent": html or _build_html_template(subject, text),
                "textContent": text,
            },
            timeout=15.0,
        )
        if r.status_code >= 400:
            logger.warning("[BREVO-API] Error %s: %s", r.status_code, r.text[:200])
            return False
        logger.info("[BREVO-API] Correo enviado a %s: '%s'", to, subject)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("[BREVO-API] Fallo HTTP: %s", exc)
        return False


def send_email(to: str, subject: str, text: str, html: str | None = None) -> dict:
    """Envia correo a traves de los canales configurados (Brevo -> Resend -> Gmail SMTP).

    Los proveedores HTTP van primero porque Render (plan gratis) bloquea SMTP y un
    intento a Gmail solo agregaria segundos de espera. Cada fallo pasa al siguiente.
    Retorna {'ok': bool, 'canal': str, 'detalle': str}; 'ok' solo es True si un
    proveedor real acepto el mensaje.
    """
    if settings.brevo_api_key and settings.brevo_sender_email:
        if send_email_via_brevo(to, subject, text, html):
            return {"ok": True, "canal": "brevo_api", "detalle": f"Enviado via Brevo a {to}"}

    if settings.resend_api_key:
        if send_email_via_resend(to, subject, text, html):
            return {"ok": True, "canal": "resend_api", "detalle": f"Enviado via Resend a {to}"}

    if settings.gmail_user and settings.gmail_app_password:
        if send_email_via_gmail(to, subject, text, html):
            return {"ok": True, "canal": "gmail_smtp", "detalle": f"Enviado via Gmail a {to}"}

    configurado = bool(
        (settings.brevo_api_key and settings.brevo_sender_email)
        or settings.resend_api_key
        or (settings.gmail_user and settings.gmail_app_password)
    )
    if settings.email_sandbox_enabled:
        logger.info("[EMAIL-SANDBOX] NO enviado. Destino: %s | Asunto: %s", to, subject)
    return {
        "ok": False,
        "canal": "ninguno",
        "detalle": (
            "Ningun proveedor de correo logro entregar el mensaje"
            if configurado
            else "Sin proveedores de correo configurados (BREVO_API_KEY, RESEND_API_KEY o GMAIL_USER/GMAIL_APP_PASSWORD)"
        ),
    }

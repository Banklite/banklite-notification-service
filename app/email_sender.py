"""Envio de correo por Resend (HTTP). Si no hay clave, no envia y devuelve False."""

import logging

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


def send_email(to: str, subject: str, text: str) -> bool:
    if not settings.resend_api_key:
        return False
    html = (
        '<div style="font-family:Arial,sans-serif;max-width:480px;margin:auto">'
        '<h2 style="color:#26474E">BankLite</h2>'
        f"<h3>{subject}</h3><p>{text}</p>"
        '<hr><p style="color:#888;font-size:12px">Proyecto academico. Nunca compartas tu clave.</p></div>'
    )
    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={"from": settings.email_from, "to": [to], "subject": subject, "html": html},
            timeout=10.0,
        )
        if r.status_code >= 400:
            logger.warning("Resend rechazo el correo (%s): %s", r.status_code, r.text[:200])
            return False
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Fallo el envio de correo: %s", exc)
        return False

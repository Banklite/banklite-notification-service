"""Envio de mensajes por WhatsApp Business Cloud API (Meta).

Requiere dos variables de entorno:
  - WHATSAPP_TOKEN: token permanente de System User (Meta Business Manager)
  - WHATSAPP_PHONE_ID: ID del numero de telefono registrado en la app de WhatsApp Business

Sin estas variables, no envia y devuelve False (el servicio sigue funcionando
solo con notificaciones in-app y correo).

Docs: https://developers.facebook.com/docs/whatsapp/cloud-api/messages/text-messages
"""

import json
import logging
import urllib.request
import urllib.error

from .config import settings

logger = logging.getLogger(__name__)

# Version del Graph API de Meta (actualizar cuando Meta deprecie)
GRAPH_API_VERSION = "v21.0"


def send_whatsapp(to_phone: str, message: str) -> bool:
    """Envia un mensaje de texto por WhatsApp.

    Args:
        to_phone: Numero del destinatario en formato internacional sin '+' (ej: 573001234567)
        message: Texto del mensaje (max 4096 chars)

    Returns:
        True si el mensaje fue aceptado por la API de Meta, False en caso contrario.
    """
    if not settings.whatsapp_token or not settings.whatsapp_phone_id:
        return False

    # Limpiar numero: solo digitos, sin '+' ni espacios
    phone = "".join(ch for ch in to_phone if ch.isdigit())
    if len(phone) < 10:
        logger.warning("WhatsApp: numero invalido %s", to_phone)
        return False

    url = (
        f"https://graph.facebook.com/{GRAPH_API_VERSION}"
        f"/{settings.whatsapp_phone_id}/messages"
    )

    payload = json.dumps({
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "text",
        "text": {"preview_url": False, "body": message[:4096]},
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", f"Bearer {settings.whatsapp_token}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            msg_id = res_data.get("messages", [{}])[0].get("id", "unknown")
            logger.info("WhatsApp enviado a %s — msg_id: %s", phone[-4:], msg_id)
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        logger.warning("WhatsApp HTTP %d: %s", e.code, body[:300])
        return False
    except Exception as exc:
        logger.warning("WhatsApp fallo: %s", exc)
        return False

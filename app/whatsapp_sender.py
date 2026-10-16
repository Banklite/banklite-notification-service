"""Envio de mensajes por WhatsApp: Green API (QR scan), CallMeBot, Meta Cloud API y Sandbox."""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

import httpx

from .config import settings

logger = logging.getLogger(__name__)


def send_whatsapp(to_phone: str, message: str) -> dict:
    """Envia un mensaje de texto por WhatsApp.

    Soporta:
    1. Green API (Escaneo de QR tipo WhatsApp Web, 100% confiable y sin limites de bot)
    2. CallMeBot API
    3. Meta WhatsApp Business Cloud API
    4. Modo Sandbox (Log local estructurado)
    """
    # Limpiar numero: solo digitos
    phone = "".join(ch for ch in to_phone if ch.isdigit())
    if len(phone) == 10 and not phone.startswith("57"):
        phone = f"57{phone}"

    if len(phone) < 10:
        logger.warning("WhatsApp: numero invalido %s", to_phone)
        return {"ok": False, "canal": "ninguno", "detalle": "Numero invalido"}

    # 1. Intentar Green API (La opcion mas confiable: vinculada por QR como WhatsApp Web)
    if settings.greenapi_instance_id and settings.greenapi_api_token:
        # Green API usa formato: 573001234567@c.us
        chat_id = f"{phone}@c.us"
        url_green = f"https://api.green-api.com/waInstance{settings.greenapi_instance_id}/sendMessage/{settings.greenapi_api_token}"
        try:
            r = httpx.post(
                url_green,
                json={"chatId": chat_id, "message": message},
                timeout=10.0,
            )
            if r.status_code == 200:
                data = r.json()
                msg_id = data.get("idMessage", "ok")
                logger.info("[GREEN-API] WhatsApp enviado a %s — idMessage: %s", phone[-4:], msg_id)
                return {
                    "ok": True,
                    "canal": "green_api",
                    "detalle": f"Enviado via Green API a +{phone} (id: {msg_id})",
                    "phone": phone,
                }
            else:
                logger.warning("[GREEN-API] Error %s: %s", r.status_code, r.text[:200])
        except Exception as exc:  # noqa: BLE001
            logger.warning("[GREEN-API] Fallo HTTP a %s: %s", phone, exc)

    # 2. Intentar CallMeBot
    if settings.callmebot_apikey:
        target_phone = f"+{phone}" if not phone.startswith("+") else phone
        encoded_msg = urllib.parse.quote(message)
        url_bot = (
            f"https://api.callmebot.com/whatsapp.php"
            f"?phone={target_phone}&text={encoded_msg}&apikey={settings.callmebot_apikey}"
        )
        try:
            req = urllib.request.Request(url_bot, headers={"User-Agent": "BankLite-WhatsApp/1.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                body = response.read().decode("utf-8")
                if "Message queued" in body or "Message sent" in body or response.status == 200:
                    logger.info("[CALLMEBOT] Mensaje WhatsApp enviado exitosamente a %s", target_phone)
                    return {
                        "ok": True,
                        "canal": "callmebot",
                        "detalle": f"Enviado via CallMeBot a {target_phone}",
                        "phone": target_phone,
                    }
        except Exception as exc:  # noqa: BLE001
            logger.warning("[CALLMEBOT] Fallo el envio a %s: %s", target_phone, exc)

    # 3. Intentar API oficial de Meta si estan las credenciales
    if settings.whatsapp_token and settings.whatsapp_phone_id:
        url = (
            f"https://graph.facebook.com/{settings.whatsapp_api_version}"
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
                logger.info("[META-WHATSAPP] Mensaje enviado a %s — msg_id: %s", phone[-4:], msg_id)
                return {
                    "ok": True,
                    "canal": "meta_cloud_api",
                    "detalle": f"Enviado a +{phone} (msg_id: {msg_id})",
                    "phone": phone,
                }
        except Exception as exc:  # noqa: BLE001
            logger.warning("[META-WHATSAPP] Fallo: %s", exc)

    # 4. Modo Sandbox: si no hay credenciales o los proveedores fallaron
    if settings.whatsapp_sandbox_enabled:
        logger.info(
            "[WHATSAPP-SANDBOX] [Destino: +%s]\n%s",
            phone,
            message,
        )
        return {
            "ok": True,
            "canal": "whatsapp_sandbox",
            "detalle": f"Notificacion WhatsApp registrada para +{phone}",
            "phone": phone,
        }

    return {"ok": False, "canal": "ninguno", "detalle": "WhatsApp no configurado"}

"""Consumidor de eventos de notification-service (comunicacion ASINCRONA).

Escucha en el exchange banklite.events:
  - transfer.completed           -> aviso de transferencia enviada / recibida
  - fraud.alert                  -> alerta de seguridad al titular de la cuenta
  - card.transaction.authorized  -> movimiento de tarjeta
y crea la notificacion en la bandeja y envia el correo, igual que el endpoint REST.
"""

import json
import logging
import threading
import time
import uuid

import httpx
import pika

from .config import settings
from .database import SessionLocal
from .models import Notificacion
from .routers.notifications import _enviar_correo_y_whatsapp

logger = logging.getLogger(__name__)

EVENT_TRANSFER_COMPLETED = "transfer.completed"
EVENT_FRAUD_ALERT = "fraud.alert"
EVENT_CARD_AUTHORIZED = "card.transaction.authorized"

_stop = threading.Event()


def _cop(monto) -> str:
    return "$" + f"{float(monto):,.0f}".replace(",", ".")


def _usuario_de_cuenta(id_cuenta: str | None) -> uuid.UUID | None:
    """Resuelve el titular de una cuenta preguntandole a account-service (REST sincrono)."""
    if not id_cuenta:
        return None
    try:
        r = httpx.get(f"{settings.account_service_url}/accounts/{id_cuenta}", timeout=settings.identity_timeout_seconds)
        if r.status_code == 200 and r.json().get("id_usuario"):
            return uuid.UUID(r.json()["id_usuario"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo resolver el titular de la cuenta %s: %s", id_cuenta, exc)
    return None


def _crear_aviso(id_usuario: uuid.UUID | None, tipo: str, titulo: str, mensaje: str) -> None:
    if id_usuario is None:
        return
    db = SessionLocal()
    try:
        n = Notificacion(id_usuario=id_usuario, tipo=tipo, titulo=titulo, mensaje=mensaje)
        db.add(n)
        db.commit()
        db.refresh(n)
        id_n = n.id_notificacion
    finally:
        db.close()
    # Correo (la funcion ya maneja errores de proveedor y marca correo_enviado)
    _enviar_correo_y_whatsapp(id_n, id_usuario, titulo, mensaje, False)


def _on_transfer_completed(p: dict) -> None:
    monto = _cop(p["monto"])
    destino = p.get("nombre_destino") or "otra cuenta"
    concepto = f" Concepto: {p['concepto']}." if p.get("concepto") else ""
    if p.get("id_usuario_origen"):
        _crear_aviso(
            uuid.UUID(p["id_usuario_origen"]),
            "transferencia_enviada",
            "Transferencia realizada",
            f"Enviaste {monto} a {destino}.{concepto} Ref: {p.get('referencia') or p['id_transferencia'][:8]}",
        )
    if p.get("id_usuario_destino"):
        _crear_aviso(
            uuid.UUID(p["id_usuario_destino"]),
            "transferencia_recibida",
            "Recibiste una transferencia",
            f"Te enviaron {monto}.{concepto}",
        )


def _on_fraud_alert(p: dict) -> None:
    id_usuario = _usuario_de_cuenta(p.get("id_cuenta"))
    monto = f" por {_cop(p['monto'])}" if p.get("monto") is not None else ""
    _crear_aviso(
        id_usuario,
        "fraude",
        "Alerta de seguridad",
        f"Detectamos una operacion inusual{monto} en tu cuenta (prioridad {p.get('prioridad')}). "
        "Si no la reconoces, bloquea tu tarjeta y contactanos.",
    )


def _on_card_authorized(p: dict) -> None:
    id_usuario = _usuario_de_cuenta(p.get("id_cuenta"))
    if p.get("resultado") == "aprobada":
        titulo, msg = "Compra con tarjeta", f"Compra aprobada por {_cop(p['monto'])} en {p.get('comercio') or 'un comercio'}."
    else:
        titulo, msg = "Compra rechazada", f"Se rechazo una compra por {_cop(p['monto'])} en {p.get('comercio') or 'un comercio'}."
    _crear_aviso(id_usuario, "movimiento_tarjeta", titulo, msg)


_HANDLERS = {
    EVENT_TRANSFER_COMPLETED: _on_transfer_completed,
    EVENT_FRAUD_ALERT: _on_fraud_alert,
    EVENT_CARD_AUTHORIZED: _on_card_authorized,
}


def _worker() -> None:
    while not _stop.is_set():
        connection = None
        try:
            connection = pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))
            channel = connection.channel()
            channel.exchange_declare(exchange=settings.events_exchange, exchange_type="topic", durable=True)
            channel.queue_declare(queue=settings.events_queue, durable=True)
            for rk in _HANDLERS:
                channel.queue_bind(queue=settings.events_queue, exchange=settings.events_exchange, routing_key=rk)

            def callback(ch, method, properties, body):
                try:
                    _HANDLERS[method.routing_key](json.loads(body.decode("utf-8")))
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Error procesando %s: %s", method.routing_key, exc)
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            channel.basic_qos(prefetch_count=10)
            channel.basic_consume(queue=settings.events_queue, on_message_callback=callback)
            logger.info("Notification consumer escuchando %s", ", ".join(_HANDLERS))
            while not _stop.is_set() and channel.is_open:
                connection.process_data_events(time_limit=1)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Notification consumer sin conexion: %s. Reintentando en 5s...", exc)
            time.sleep(5)
        finally:
            if connection and connection.is_open:
                connection.close()


def start_consumer() -> None:
    if not settings.enable_consumer:
        logger.info("Consumidor de eventos deshabilitado (ENABLE_CONSUMER=false)")
        return
    _stop.clear()
    threading.Thread(target=_worker, daemon=True, name="notification-consumer").start()


def stop_consumer() -> None:
    _stop.set()

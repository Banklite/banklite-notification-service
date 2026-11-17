"""Pruebas de INTEGRACION de notification-service: endpoint + base de datos + despacho.

La base es SQLite en memoria. identity-service y los proveedores de correo/WhatsApp
se reemplazan con mocks (no se envia ningun mensaje real).
"""
import uuid
from unittest.mock import patch

import httpx
import pytest

from app import consumer
from app.models import Notificacion

ID_USUARIO = uuid.uuid4()
CORREO_OK = {"ok": True, "canal": "brevo_api", "detalle": "Enviado via Brevo"}
SIN_ENTREGA = {"ok": False, "canal": "ninguno", "detalle": "Sin proveedores"}


@pytest.fixture(autouse=True)
def externos(sesiones):
    with (
        patch("app.routers.notifications.SessionLocal", sesiones),
        patch("app.consumer.SessionLocal", sesiones),
        patch("app.routers.notifications.get_user_email", return_value="juan@example.com") as email,
        patch("app.routers.notifications._get_user_phone", return_value=None),
        patch("app.routers.notifications.send_email", return_value=CORREO_OK) as enviar_correo,
        patch("app.routers.notifications.send_whatsapp", return_value=SIN_ENTREGA) as enviar_whatsapp,
    ):
        yield {"email": email, "enviar_correo": enviar_correo, "enviar_whatsapp": enviar_whatsapp}


def _crear(client, **extra) -> dict:
    cuerpo = {"id_usuario": str(ID_USUARIO), "tipo": "transferencia_recibida", "titulo": "Recibiste una transferencia", "mensaje": "Te enviaron $50.000"}
    r = client.post("/notifications", json={**cuerpo, **extra})
    assert r.status_code == 201
    return r.json()


def test_crear_aviso_lo_guarda_y_envia_el_correo_en_segundo_plano(client, sesiones, externos):
    creado = _crear(client)

    assert creado["leida"] is False
    externos["enviar_correo"].assert_called_once_with("juan@example.com", "Recibiste una transferencia", "Te enviaron $50.000")
    with sesiones() as db:
        guardada = db.get(Notificacion, uuid.UUID(creado["id_notificacion"]))
        assert guardada.correo_enviado is True  # la tarea en segundo plano marco el envio


def test_si_el_correo_falla_el_aviso_queda_sin_marcar(client, sesiones, externos):
    externos["enviar_correo"].return_value = SIN_ENTREGA

    creado = _crear(client)

    with sesiones() as db:
        assert db.get(Notificacion, uuid.UUID(creado["id_notificacion"])).correo_enviado is False


def test_aviso_solo_en_la_app_no_envia_correo(client, externos):
    _crear(client, enviar_correo=False)
    externos["enviar_correo"].assert_not_called()


def test_bandeja_del_usuario_y_marcado_de_leidas(client):
    primera = _crear(client)
    _crear(client, titulo="Compra con tarjeta")
    _crear(client, id_usuario=str(uuid.uuid4()))  # aviso de otro usuario

    assert len(client.get("/notifications", params={"id_usuario": str(ID_USUARIO)}).json()) == 2

    leida = client.patch(f"/notifications/{primera['id_notificacion']}/read")
    assert leida.json()["leida"] is True
    pendientes = client.get("/notifications", params={"id_usuario": str(ID_USUARIO), "solo_no_leidas": True}).json()
    assert [n["titulo"] for n in pendientes] == ["Compra con tarjeta"]

    assert client.post("/notifications/read-all", params={"id_usuario": str(ID_USUARIO)}).status_code == 204
    assert client.get("/notifications", params={"id_usuario": str(ID_USUARIO), "solo_no_leidas": True}).json() == []
    assert client.get("/stats").json() == {"total_notificaciones": 3}


def test_marcar_como_leida_una_notificacion_inexistente_responde_404(client):
    assert client.patch(f"/notifications/{uuid.uuid4()}/read").status_code == 404


def test_codigo_de_seguridad_entregado_no_guarda_el_codigo_en_la_base(client, sesiones, externos):
    r = client.post("/notifications/codigo-seguridad", json={
        "id_usuario": str(ID_USUARIO), "titulo": "Codigo de verificacion", "mensaje": "Tu codigo es 482913", "enviar_whatsapp": False,
    })

    assert r.status_code == 200 and r.json()["entregado"] is True
    externos["enviar_correo"].assert_called_once_with("juan@example.com", "Codigo de verificacion", "Tu codigo es 482913")
    with sesiones() as db:
        aviso = db.query(Notificacion).one()
        assert aviso.tipo == "seguridad" and "482913" not in aviso.mensaje and aviso.correo_enviado is True


def test_codigo_de_seguridad_no_entregado_responde_502(client, externos):
    externos["enviar_correo"].return_value = SIN_ENTREGA

    r = client.post("/notifications/codigo-seguridad", json={
        "id_usuario": str(ID_USUARIO), "titulo": "Codigo de verificacion", "mensaje": "Tu codigo es 482913",
    })

    assert r.status_code == 502 and "No se pudo entregar" in r.json()["detail"]


def test_usuario_sin_correo_registrado_tambien_responde_502(client, externos):
    externos["email"].return_value = None

    r = client.post("/notifications/codigo-seguridad", json={
        "id_usuario": str(ID_USUARIO), "titulo": "Codigo", "mensaje": "Tu codigo es 111222",
    })

    assert r.status_code == 502
    externos["enviar_correo"].assert_not_called()


def test_envio_directo_de_correo(client, externos):
    cuerpo = {"to_email": "cliente@example.com", "subject": "Prueba", "message": "Hola"}

    assert client.post("/notifications/send-email", json=cuerpo).json()["canal"] == "brevo_api"

    externos["enviar_correo"].return_value = SIN_ENTREGA
    assert client.post("/notifications/send-email", json=cuerpo).status_code == 502


def test_envio_directo_de_whatsapp_sin_proveedor_responde_400(client):
    r = client.post("/notifications/send-whatsapp", json={"to_phone": "3001234567", "message": "Hola"})
    assert r.status_code == 400


def test_estado_de_los_canales(client):
    r = client.get("/notifications/channels/status")
    assert r.status_code == 200
    assert set(r.json()) >= {"brevo_configured", "gmail_configured", "resend_configured", "whatsapp_configured"}


def test_evento_de_compra_con_tarjeta_crea_el_aviso_del_titular(client, sesiones, externos):
    """Flujo asincrono completo: evento de card-service -> account-service (mock) -> base -> correo."""
    cuenta = httpx.Response(200, json={"id_usuario": str(ID_USUARIO)})
    with patch("app.consumer.httpx.get", return_value=cuenta):
        consumer._on_card_authorized({"id_cuenta": str(uuid.uuid4()), "resultado": "aprobada", "monto": 89900, "comercio": "Exito"})

    avisos = client.get("/notifications", params={"id_usuario": str(ID_USUARIO)}).json()
    assert [(a["tipo"], a["mensaje"]) for a in avisos] == [("movimiento_tarjeta", "Compra aprobada por $89.900 en Exito.")]
    assert avisos[0]["correo_enviado"] is True
    externos["enviar_whatsapp"].assert_not_called()  # los avisos por evento solo van por correo


def test_evento_sin_titular_resoluble_no_crea_aviso(sesiones):
    with patch("app.consumer.httpx.get", side_effect=httpx.ConnectError("account-service caido")):
        consumer._on_fraud_alert({"id_cuenta": str(uuid.uuid4()), "monto": 100, "prioridad": "media"})

    with sesiones() as db:
        assert db.query(Notificacion).count() == 0

"""Pruebas UNITARIAS del envio de correo (cadena de proveedores Brevo -> Resend -> Gmail).

Los proveedores reales se reemplazan con mocks de httpx.post: se comprueba el orden,
el respaldo y que un envio fallido NUNCA se reporta como exitoso.
"""
from unittest.mock import patch

import httpx
import pytest

from app import email_sender
from app.config import settings

PROVEEDORES = (
    "brevo_api_key", "brevo_sender_email", "resend_api_key", "gmail_user", "gmail_app_password",
)


@pytest.fixture(autouse=True)
def sin_proveedores(monkeypatch):
    """Cada prueba parte sin ningun proveedor configurado y activa solo los que necesita."""
    for campo in PROVEEDORES:
        monkeypatch.setattr(settings, campo, None)
    monkeypatch.setattr(settings, "email_sandbox_enabled", False)


def _respuestas(por_dominio: dict):
    llamadas = []

    def fake_post(url, **kwargs):
        llamadas.append((url, kwargs))
        for dominio, status in por_dominio.items():
            if dominio in url:
                return httpx.Response(status, json={})
        raise httpx.ConnectError("sin red")

    return fake_post, llamadas


def test_brevo_entrega_el_correo_con_el_remitente_verificado(monkeypatch):
    monkeypatch.setattr(settings, "brevo_api_key", "clave-brevo")
    monkeypatch.setattr(settings, "brevo_sender_email", "banklite@example.com")
    fake, llamadas = _respuestas({"brevo.com": 201})

    with patch("app.email_sender.httpx.post", side_effect=fake):
        resultado = email_sender.send_email("cliente@example.com", "Codigo de seguridad", "Tu codigo es 482913")

    assert resultado == {"ok": True, "canal": "brevo_api", "detalle": "Enviado via Brevo a cliente@example.com"}
    url, kwargs = llamadas[0]
    assert kwargs["headers"]["api-key"] == "clave-brevo"
    assert kwargs["json"]["sender"]["email"] == "banklite@example.com"
    assert kwargs["json"]["to"] == [{"email": "cliente@example.com"}]
    assert "482913" in kwargs["json"]["htmlContent"]


def test_si_brevo_falla_se_intenta_con_resend(monkeypatch):
    monkeypatch.setattr(settings, "brevo_api_key", "clave-brevo")
    monkeypatch.setattr(settings, "brevo_sender_email", "banklite@example.com")
    monkeypatch.setattr(settings, "resend_api_key", "clave-resend")
    fake, llamadas = _respuestas({"brevo.com": 401, "resend.com": 200})

    with patch("app.email_sender.httpx.post", side_effect=fake):
        resultado = email_sender.send_email("cliente@example.com", "Aviso", "Hola")

    assert resultado["ok"] is True and resultado["canal"] == "resend_api"
    assert [url.split("/")[2] for url, _ in llamadas] == ["api.brevo.com", "api.resend.com"]


def test_si_todos_los_proveedores_fallan_se_informa_como_no_entregado(monkeypatch):
    monkeypatch.setattr(settings, "brevo_api_key", "clave-brevo")
    monkeypatch.setattr(settings, "brevo_sender_email", "banklite@example.com")
    fake, _ = _respuestas({})  # error de red

    with patch("app.email_sender.httpx.post", side_effect=fake):
        resultado = email_sender.send_email("cliente@example.com", "Aviso", "Hola")

    assert resultado["ok"] is False and resultado["canal"] == "ninguno"
    assert "Ningun proveedor" in resultado["detalle"]


def test_sin_proveedores_configurados_no_se_llama_a_nadie():
    with patch("app.email_sender.httpx.post") as mock_post:
        resultado = email_sender.send_email("cliente@example.com", "Aviso", "Hola")

    assert resultado["ok"] is False and "Sin proveedores" in resultado["detalle"]
    mock_post.assert_not_called()


def test_el_modo_sandbox_tampoco_cuenta_como_entregado(monkeypatch):
    monkeypatch.setattr(settings, "email_sandbox_enabled", True)
    assert email_sender.send_email("cliente@example.com", "Aviso", "Hola")["ok"] is False


def test_gmail_smtp_es_el_ultimo_recurso(monkeypatch):
    monkeypatch.setattr(settings, "gmail_user", "banklite@gmail.com")
    monkeypatch.setattr(settings, "gmail_app_password", "clave-de-app")

    with patch("app.email_sender.smtplib.SMTP") as mock_smtp:
        resultado = email_sender.send_email("cliente@example.com", "Aviso", "Hola")

    assert resultado["canal"] == "gmail_smtp"
    servidor = mock_smtp.return_value
    servidor.starttls.assert_called_once()
    servidor.login.assert_called_once_with("banklite@gmail.com", "clave-de-app")
    assert servidor.sendmail.call_args.args[1] == ["cliente@example.com"]


def test_correo_del_usuario_se_consulta_a_identity_service():
    with patch("app.email_sender.httpx.get", return_value=httpx.Response(200, json={"email": "juan@example.com"})) as mock_get:
        assert email_sender.get_user_email("abc-123") == "juan@example.com"
    assert mock_get.call_args.args[0].endswith("/users/abc-123")


@pytest.mark.parametrize("respuesta", [httpx.Response(404, json={}), httpx.ConnectError("identity caido")])
def test_usuario_sin_correo_resoluble_devuelve_none(respuesta):
    efecto = {"side_effect": respuesta} if isinstance(respuesta, Exception) else {"return_value": respuesta}
    with patch("app.email_sender.httpx.get", **efecto):
        assert email_sender.get_user_email("abc-123") is None

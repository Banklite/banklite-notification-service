"""Pruebas UNITARIAS de la redaccion de los avisos (logica pura del consumidor de eventos)."""
import uuid
from unittest.mock import patch

import pytest

from app import consumer


@pytest.mark.parametrize("monto, esperado", [
    (1500000, "$1.500.000"), ("89900.00", "$89.900"), (0, "$0"), (999.6, "$1.000"),
])
def test_formato_de_pesos_colombianos(monto, esperado):
    assert consumer._cop(monto) == esperado


def test_transferencia_completada_avisa_a_quien_envia_y_a_quien_recibe():
    origen, destino = uuid.uuid4(), uuid.uuid4()
    evento = {
        "id_transferencia": str(uuid.uuid4()), "monto": "250000", "nombre_destino": "Camilo Beltran",
        "concepto": "Arriendo", "referencia": "BL-20261110-AB12",
        "id_usuario_origen": str(origen), "id_usuario_destino": str(destino),
    }

    with patch("app.consumer._crear_aviso") as mock_aviso:
        consumer._on_transfer_completed(evento)

    enviado, recibido = [llamada.args for llamada in mock_aviso.call_args_list]
    assert enviado == (origen, "transferencia_enviada", "Transferencia realizada",
                       "Enviaste $250.000 a Camilo Beltran. Concepto: Arriendo. Ref: BL-20261110-AB12")
    assert recibido == (destino, "transferencia_recibida", "Recibiste una transferencia",
                        "Te enviaron $250.000. Concepto: Arriendo.")


def test_transferencia_a_otro_banco_solo_avisa_al_origen():
    evento = {"id_transferencia": "0f8fad5b-d9cb-469f-a165-70867728950e", "monto": "1000", "id_usuario_origen": str(uuid.uuid4())}

    with patch("app.consumer._crear_aviso") as mock_aviso:
        consumer._on_transfer_completed(evento)

    assert mock_aviso.call_count == 1
    assert mock_aviso.call_args.args[3] == "Enviaste $1.000 a otra cuenta. Ref: 0f8fad5b"


@pytest.mark.parametrize("resultado, titulo, verbo", [
    ("aprobada", "Compra con tarjeta", "Compra aprobada"),
    ("rechazada", "Compra rechazada", "Se rechazo una compra"),
])
def test_aviso_de_compra_con_tarjeta_segun_el_resultado(resultado, titulo, verbo):
    id_usuario = uuid.uuid4()
    with (
        patch("app.consumer._usuario_de_cuenta", return_value=id_usuario),
        patch("app.consumer._crear_aviso") as mock_aviso,
    ):
        consumer._on_card_authorized({"id_cuenta": "c1", "resultado": resultado, "monto": 89900, "comercio": "Exito"})

    assert mock_aviso.call_args.args == (id_usuario, "movimiento_tarjeta", titulo, f"{verbo} por $89.900 en Exito.")


def test_alerta_de_fraude_incluye_monto_y_prioridad():
    with (
        patch("app.consumer._usuario_de_cuenta", return_value=uuid.uuid4()),
        patch("app.consumer._crear_aviso") as mock_aviso,
    ):
        consumer._on_fraud_alert({"id_cuenta": "c1", "monto": 6000000, "prioridad": "alta"})

    _, tipo, titulo, mensaje = mock_aviso.call_args.args
    assert (tipo, titulo) == ("fraude", "Alerta de seguridad")
    assert "por $6.000.000" in mensaje and "prioridad alta" in mensaje

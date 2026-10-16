import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal, get_db
from ..email_sender import get_user_email, send_email
from ..models import Notificacion
from ..schemas import (
    ChannelStatusOut,
    DirectEmailSend,
    DirectWhatsAppSend,
    NotificacionCreate,
    NotificacionOut,
)
from ..whatsapp_sender import send_whatsapp

router = APIRouter(prefix="/notifications", tags=["notificaciones"])


def _get_user_phone(id_usuario: uuid.UUID) -> str | None:
    """Consulta el telefono del usuario a identity-service."""
    import httpx
    try:
        r = httpx.get(
            f"{settings.identity_service_url}/users/{id_usuario}",
            timeout=settings.identity_timeout_seconds,
        )
        if r.status_code == 200:
            return r.json().get("telefono")
    except Exception:
        pass
    return None


def _enviar_correo_y_whatsapp(
    id_notificacion: uuid.UUID, id_usuario: uuid.UUID, titulo: str, mensaje: str
) -> None:
    """Tarea en segundo plano: envia correo y/o WhatsApp sin retrasar la respuesta."""
    correo_resultado = {"ok": False}
    whatsapp_resultado = {"ok": False}

    # 1. Correo
    email = get_user_email(id_usuario)
    if email:
        correo_resultado = send_email(email, titulo, mensaje)

    # 2. WhatsApp
    phone = _get_user_phone(id_usuario)
    if phone:
        texto_wa = f"*BankLite* - {titulo}\n\n{mensaje}"
        whatsapp_resultado = send_whatsapp(phone, texto_wa)

    # Actualizar flags en la notificacion si se envio o simulo exitosamente
    if correo_resultado.get("ok") or whatsapp_resultado.get("ok"):
        with SessionLocal() as db:
            n = db.get(Notificacion, id_notificacion)
            if n:
                if correo_resultado.get("ok"):
                    n.correo_enviado = True
                db.commit()


@router.get("/channels/status", response_model=ChannelStatusOut)
def get_channel_status():
    """Retorna el estado de los canales de salida de notificaciones (Gmail, Resend, WhatsApp)."""
    return ChannelStatusOut(
        gmail_configured=bool(settings.gmail_user and settings.gmail_app_password),
        resend_configured=bool(settings.resend_api_key),
        whatsapp_configured=bool(
            (settings.whatsapp_token and settings.whatsapp_phone_id)
            or (settings.greenapi_instance_id and settings.greenapi_api_token)
            or settings.callmebot_apikey
        ),
        email_sandbox_active=settings.email_sandbox_enabled,
        whatsapp_sandbox_active=settings.whatsapp_sandbox_enabled,
    )


@router.post("/send-email", status_code=status.HTTP_200_OK)
def direct_send_email(payload: DirectEmailSend):
    """API directa para enviar un correo electronico por Gmail SMTP / Resend."""
    resultado = send_email(payload.to_email, payload.subject, payload.message, payload.html_content)
    if not resultado.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Fallo el envio de correo: {resultado.get('detalle')}",
        )
    return resultado


@router.post("/send-whatsapp", status_code=status.HTTP_200_OK)
def direct_send_whatsapp(payload: DirectWhatsAppSend):
    """API directa para enviar una notificacion por WhatsApp."""
    resultado = send_whatsapp(payload.to_phone, payload.message)
    if not resultado.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Fallo el envio de WhatsApp: {resultado.get('detalle')}",
        )
    return resultado


@router.post("", response_model=NotificacionOut, status_code=status.HTTP_201_CREATED)
def crear_notificacion(payload: NotificacionCreate, tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Crea un aviso y dispara el despacho asincrono por Email y WhatsApp."""
    n = Notificacion(
        id_usuario=payload.id_usuario, tipo=payload.tipo, titulo=payload.titulo, mensaje=payload.mensaje
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    if payload.enviar_correo:
        tasks.add_task(_enviar_correo_y_whatsapp, n.id_notificacion, n.id_usuario, n.titulo, n.mensaje)
    return n


@router.get("", response_model=list[NotificacionOut])
def listar(
    id_usuario: uuid.UUID,
    solo_no_leidas: bool = Query(default=False),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    stmt = select(Notificacion).where(Notificacion.id_usuario == id_usuario)
    if solo_no_leidas:
        stmt = stmt.where(Notificacion.leida.is_(False))
    stmt = stmt.order_by(Notificacion.fecha.desc()).limit(limit)
    return db.execute(stmt).scalars().all()


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def marcar_todas(id_usuario: uuid.UUID, db: Session = Depends(get_db)):
    db.execute(update(Notificacion).where(Notificacion.id_usuario == id_usuario).values(leida=True))
    db.commit()


@router.patch("/{id_notificacion}/read", response_model=NotificacionOut)
def marcar_leida(id_notificacion: uuid.UUID, db: Session = Depends(get_db)):
    n = db.get(Notificacion, id_notificacion)
    if n is None:
        raise HTTPException(status_code=404, detail="No existe la notificacion")
    n.leida = True
    db.commit()
    db.refresh(n)
    return n

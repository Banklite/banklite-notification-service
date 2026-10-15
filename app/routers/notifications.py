import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..email_sender import get_user_email, send_email
from ..whatsapp_sender import send_whatsapp
from ..models import Notificacion
from ..schemas import NotificacionCreate, NotificacionOut

router = APIRouter(prefix="/notifications", tags=["notificaciones"])


def _get_user_phone(id_usuario: uuid.UUID) -> str | None:
    """Consulta el telefono del usuario a identity-service."""
    import httpx
    from ..config import settings
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
    correo_ok = False
    whatsapp_ok = False

    # 1. Correo
    email = get_user_email(id_usuario)
    if email:
        correo_ok = send_email(email, titulo, mensaje)

    # 2. WhatsApp
    phone = _get_user_phone(id_usuario)
    if phone:
        texto_wa = f"*BankLite* - {titulo}\n\n{mensaje}"
        whatsapp_ok = send_whatsapp(phone, texto_wa)

    # Actualizar flags en la notificacion
    if correo_ok or whatsapp_ok:
        with SessionLocal() as db:
            n = db.get(Notificacion, id_notificacion)
            if n:
                if correo_ok:
                    n.correo_enviado = True
                db.commit()


@router.post("", response_model=NotificacionOut, status_code=status.HTTP_201_CREATED)
def crear_notificacion(payload: NotificacionCreate, tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Crea un aviso (lo llama transfer-service u otros servicios) y opcionalmente envia correo."""
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

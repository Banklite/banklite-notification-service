import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Notificacion(Base):
    """Tabla notificacion: aviso para un usuario (en la app y/o por correo)."""

    __tablename__ = "notificacion"
    __table_args__ = (Index("idx_notificacion_usuario", "id_usuario", "leida"),)

    id_notificacion: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    id_usuario: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    tipo: Mapped[str] = mapped_column(String(40), nullable=False)  # transferencia_enviada, transferencia_recibida, fraude...
    titulo: Mapped[str] = mapped_column(String(120), nullable=False)
    mensaje: Mapped[str] = mapped_column(Text, nullable=False)
    leida: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    correo_enviado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

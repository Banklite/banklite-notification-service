import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NotificacionCreate(BaseModel):
    id_usuario: uuid.UUID
    tipo: str = Field(max_length=40)
    titulo: str = Field(max_length=120)
    mensaje: str
    enviar_correo: bool = True


class NotificacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_notificacion: uuid.UUID
    id_usuario: uuid.UUID
    tipo: str
    titulo: str
    mensaje: str
    leida: bool
    correo_enviado: bool
    fecha: datetime

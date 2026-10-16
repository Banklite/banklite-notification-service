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


class DirectEmailSend(BaseModel):
    to_email: str
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1)
    html_content: str | None = None


class DirectWhatsAppSend(BaseModel):
    to_phone: str = Field(min_length=7, max_length=20)
    message: str = Field(min_length=1, max_length=4096)


class ChannelStatusOut(BaseModel):
    gmail_configured: bool
    resend_configured: bool
    whatsapp_configured: bool
    email_sandbox_active: bool
    whatsapp_sandbox_active: bool

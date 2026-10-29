# Notification Service — BankLite

Avisos al usuario (bandeja dentro de la app y correo): transferencias, alertas de fraude, movimientos de tarjeta y codigos de seguridad.

Parte del proyecto **BankLite** (banca digital con microservicios) de *Arquitectura y Modelamiento de Software*, Universidad Cooperativa de Colombia. Cada microservicio tiene su propio repositorio y su propia base de datos (`notification_db`).

## Responsabilidad en la arquitectura

Avisos al usuario (bandeja dentro de la app y correo): transferencias, alertas de fraude, movimientos de tarjeta y codigos de seguridad. Se comunica con los demas servicios por **REST** (operaciones que necesitan respuesta inmediata) y por **eventos** en RabbitMQ (exchange `banklite.events`, tipo topic).

| Eventos publicados | Eventos consumidos |
|---|---|
| — | `transfer.completed`, `fraud.alert`, `card.transaction.authorized` |

## Tecnologias

FastAPI, SQLAlchemy, PostgreSQL, RabbitMQ (pika). Correo por Brevo (HTTP). Python 3.12, Docker.

## Despliegue

- URL publica: <https://banklite-notification-service.onrender.com>
- Salud: <https://banklite-notification-service.onrender.com/health>
- Documentacion interactiva (Swagger): <https://banklite-notification-service.onrender.com/docs>

Desplegado en Render (plan gratuito: tarda hasta ~1 minuto en responder si estuvo inactivo). Las credenciales se configuran como variables de entorno en la plataforma, no en el codigo.

## Endpoints principales

| Metodo | Ruta | Descripcion |
|---|---|---|
| `POST` | `/notifications` | Crea un aviso (REST) |
| `GET` | `/notifications` | Bandeja del usuario |
| `PATCH` | `/notifications/{id}/read` | Marca un aviso como leido |
| `POST` | `/notifications/read-all` | Marca todos como leidos |
| `POST` | `/notifications/codigo-seguridad` | Envia un codigo de seguridad por correo |
| `POST` | `/notifications/send-email` | Envio directo de correo |
| `GET` | `/notifications/channels/status` | Estado de los canales |
| `GET` | `/health` | Estado del servicio |
| `GET` | `/stats` | Contadores del servicio |

La lista completa esta en `/docs`.

## Variables de entorno

Copia `.env.example` a `.env` y completa los valores.

| Variable | Descripcion |
|---|---|
| `DATABASE_URL` | Conexion PostgreSQL |
| `IDENTITY_SERVICE_URL` | URL de identity-service (email del usuario) |
| `ACCOUNT_SERVICE_URL` | URL de account-service (titular de la cuenta) |
| `BREVO_API_KEY` | API key de Brevo |
| `BREVO_SENDER_EMAIL` | Remitente verificado en Brevo |
| `BREVO_SENDER_NAME` | Nombre del remitente |
| `RABBITMQ_URL` | URL del bus de eventos |
| `EVENTS_QUEUE` | Cola propia |
| `ENABLE_CONSUMER` | Consumir eventos |

## Base de datos

Motor: PostgreSQL. Base: `notification_db`.

- `db/schema.sql`: creacion de tablas, indices y restricciones.
- `db/seed.sql`: datos de ejemplo.

El servicio tambien crea las tablas solo al arrancar (`create_all`). Para restaurar a mano:

```bash
createdb notification_db
psql -d notification_db -f db/schema.sql
psql -d notification_db -f db/seed.sql
```

Respaldo completo (para entregar o restaurar): `pg_dump -Fc notification_db > notification_db.dump` y `pg_restore -d notification_db notification_db.dump`.

## Instalacion y ejecucion

Con Docker:

```bash
docker build -t banklite-notification-service .
docker run --env-file .env -p 8007:8007 -e PORT=8007 banklite-notification-service
```

Sin Docker:

```bash
python -m venv .venv && source .venv/bin/activate   # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8007
```

Prueba: abre <http://localhost:8007/docs>.

## Repositorios del proyecto

`banklite-identity-service`, `banklite-account-service`, `banklite-ledger-service`, `banklite-transfer-service`, `banklite-card-service`, `banklite-fraud-service`, `banklite-notification-service`, `banklite-compliance-service`. Panel web: `services/web-panel` en el repositorio `banklite-microservicios`.

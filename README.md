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

## Pruebas automatizadas

```bash
pip install -r requirements-dev.txt
python -m pytest tests -v --cov=app --cov-report=term-missing --cov-report=html
```

No necesitan PostgreSQL, RabbitMQ ni los otros microservicios: la base es SQLite en memoria y las dependencias externas se reemplazan con mocks (`unittest.mock`). El reporte navegable queda en `htmlcov/index.html`.

| Tipo | Archivo | Que verifica |
|---|---|---|
| Unitaria (mocks) | `tests/unit/test_email_sender.py` | Cadena de proveedores de correo Brevo -> Resend -> Gmail con `httpx` y `smtplib` simulados; un envio fallido nunca se reporta como entregado. |
| Unitaria (mocks) | `tests/unit/test_mensajes.py` | Texto de los avisos por evento (transferencia, compra con tarjeta, fraude) y formato de pesos colombianos. |
| Integracion | `tests/integration/test_notifications_api.py` | Crear aviso -> base -> envio en segundo plano; bandeja y leidas; codigo de seguridad que no se guarda en la base; evento de card-service que termina en un aviso al titular. |

Resultado actual: **32 pruebas** (18 unitarias y 14 de integracion), todas aprobadas, con **75 % de cobertura** de `app/`.

En GitHub Actions las pruebas corren en cada `push` y `pull request`. Si una falla, la imagen no se construye y no se despliega. El reporte de cobertura queda en el resumen de la ejecucion y como artefacto descargable `coverage-banklite-notification-service`.

## Repositorios del proyecto

`banklite-identity-service`, `banklite-account-service`, `banklite-ledger-service`, `banklite-transfer-service`, `banklite-card-service`, `banklite-fraud-service`, `banklite-notification-service`, `banklite-compliance-service`. Panel web: `services/web-panel` en el repositorio `banklite-microservicios`.

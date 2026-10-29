-- Esquema de notification-service (PostgreSQL). Generado a partir de los modelos SQLAlchemy.
-- Tambien se crea solo al arrancar el servicio (Base.metadata.create_all).

CREATE TABLE notificacion (
	id_notificacion UUID NOT NULL, 
	id_usuario UUID NOT NULL, 
	tipo VARCHAR(40) NOT NULL, 
	titulo VARCHAR(120) NOT NULL, 
	mensaje TEXT NOT NULL, 
	leida BOOLEAN NOT NULL, 
	correo_enviado BOOLEAN NOT NULL, 
	fecha TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id_notificacion)
);
CREATE INDEX idx_notificacion_usuario ON notificacion (id_usuario, leida);

-- Datos de ejemplo de notification-service. Ejecutar despues de schema.sql.
INSERT INTO notificacion (id_notificacion, id_usuario, tipo, titulo, mensaje, leida, correo_enviado, fecha) VALUES
 ('90000000-0000-0000-0000-000000000001','11111111-1111-1111-1111-111111111111','transferencia_enviada','Transferencia realizada','Enviaste $50.000 a Luis Demo. Ref: SEED-TRF-0001',false,false,now()),
 ('90000000-0000-0000-0000-000000000002','22222222-2222-2222-2222-222222222222','transferencia_recibida','Recibiste una transferencia','Te enviaron $50.000.',false,false,now())
ON CONFLICT DO NOTHING;

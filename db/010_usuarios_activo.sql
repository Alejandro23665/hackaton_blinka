-- Paso 10: perfiles activos e inactivos. Un administrador puede desactivar un perfil: deja de poder
-- iniciar sesión y sus sesiones abiertas se cierran, pero sus documentos y correcciones se conservan.
ALTER TABLE usuarios ADD COLUMN activo BOOLEAN NOT NULL DEFAULT true;

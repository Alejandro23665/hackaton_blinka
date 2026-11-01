-- Paso 12: no todo lo que no se pudo leer va a revisión humana. Una fecha o un folio ilegibles, o un
-- documento sin ninguno de los tres montos principales, quedan NO_LEGIBLE fuera de la cola. La
-- decisión de escalar la toma el procesamiento y queda en la columna escalado.
ALTER TABLE documentos_procesados ADD COLUMN escalado BOOLEAN NOT NULL DEFAULT FALSE;

-- Los documentos ya guardados conservan el criterio anterior
UPDATE documentos_procesados SET escalado = observaciones IN ('NO_LEGIBLE', 'DESCUADRE');

DROP INDEX ix_documentos_procesados_revision;
ALTER TABLE documentos_procesados DROP COLUMN requiere_revision;
ALTER TABLE documentos_procesados
    ADD COLUMN requiere_revision BOOLEAN GENERATED ALWAYS AS (escalado AND revisado_en IS NULL) STORED;
CREATE INDEX ix_documentos_procesados_revision ON documentos_procesados (creado_en) WHERE requiere_revision;

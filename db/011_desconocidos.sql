-- Paso 11: los documentos desconocidos ya no se descartan: se registran con el tipo DESC, RUT 1-9 y
-- folio 0000 (imagen DESC_1-9_0000), sin leer sus datos. Su observación es DESCONOCIDO y no van a
-- revisión humana.
ALTER TABLE tipos_documentos ALTER COLUMN documento TYPE VARCHAR(4);
ALTER TABLE tipos_documentos DROP CONSTRAINT tipos_documentos_documento_check;
ALTER TABLE tipos_documentos ADD CONSTRAINT tipos_documentos_documento_check
    CHECK (documento IN ('FC', 'CI', 'GD', 'DESC'));
INSERT INTO tipos_documentos (documento) VALUES ('DESC');

ALTER TABLE documentos_procesados DROP CONSTRAINT documentos_procesados_observaciones_check;
ALTER TABLE documentos_procesados ADD CONSTRAINT documentos_procesados_observaciones_check
    CHECK (observaciones IN ('LEGIBLE', 'NO_LEGIBLE', 'DESCUADRE', 'DESCONOCIDO'));

-- requiere_revision: solo los no legibles y los descuadres que nadie ha revisado (no los desconocidos)
DROP INDEX ix_documentos_procesados_revision;
ALTER TABLE documentos_procesados DROP COLUMN requiere_revision;
ALTER TABLE documentos_procesados
    ADD COLUMN requiere_revision BOOLEAN GENERATED ALWAYS AS
        (observaciones IN ('NO_LEGIBLE', 'DESCUADRE') AND revisado_en IS NULL) STORED;
CREATE INDEX ix_documentos_procesados_revision ON documentos_procesados (creado_en) WHERE requiere_revision;

-- Paso 3: decisiones sobre documentos_procesados.
-- - Los documentos desconocidos se descartan: no se guardan (el tipo sigue siendo obligatorio).
-- - El monto exento va sumado dentro de impuestos.
-- - Los no legibles y los descuadrados se escalan a revisión humana.
-- - Todo el sistema es del proyecto Oxxo: no hay tabla de proyectos.

COMMENT ON COLUMN documentos_procesados.impuestos IS
    'Otros impuestos (IABA, ILA...) más el monto exento. El IVA va aparte. total_neto + iva + impuestos = total';

-- Tercer valor: legible pero la suma no da el total
ALTER TABLE documentos_procesados DROP CONSTRAINT documentos_procesados_observaciones_check;
ALTER TABLE documentos_procesados ADD CONSTRAINT documentos_procesados_observaciones_check
    CHECK (observaciones IN ('LEGIBLE', 'NO_LEGIBLE', 'DESCUADRE'));

-- Se calcula sola a partir de observaciones: nadie la puede poner a mano
ALTER TABLE documentos_procesados
    ADD COLUMN requiere_revision BOOLEAN GENERATED ALWAYS AS (observaciones <> 'LEGIBLE') STORED;

-- La cola de revisión: solo los que la requieren
CREATE INDEX ix_documentos_procesados_revision ON documentos_procesados (creado_en)
    WHERE requiere_revision;

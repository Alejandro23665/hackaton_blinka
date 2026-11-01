-- Paso 13: la revisión humana es selectiva. Van a la cola los descuadres confirmados, los tipos deducidos
-- sin ver el título y los documentos desconocidos (también las notas de crédito). La mala calidad de la
-- imagen no basta: un campo ilegible deja el documento NO_LEGIBLE, fuera de la cola.
-- Las guías guardan su denominación impresa, que decide su RUT fijo:
-- «Guía de Despacho» → 94851000-6; «Guía Electrónica» (o «Guía de Despacho Electrónica») → 76084682-1.
ALTER TABLE documentos_procesados ADD COLUMN denominacion VARCHAR(20)
    CHECK (denominacion IN ('GUIA_DESPACHO', 'GUIA_ELECTRONICA'));

-- Los desconocidos ya registrados pasan a la cola
UPDATE documentos_procesados SET escalado = TRUE WHERE observaciones = 'DESCONOCIDO';

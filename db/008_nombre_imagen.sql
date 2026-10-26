-- Paso 8: la columna imagen guarda el nombre del archivo del documento, TIPO_RUT_FOLIO más su extensión
-- (por ejemplo FC_93178000-K_23193169.png). Lo que falta queda vacío (FC__1458754.png); un RUT ilegible se
-- omite. Se asigna al guardar los datos extraídos y cambia si una persona corrige tipo, RUT o folio.
COMMENT ON COLUMN documentos_procesados.imagen IS
    'Nombre del archivo del documento: TIPO_RUT_FOLIO.ext (vacío lo que falta; sin RUT 1-9); en documentos/ del almacenamiento';

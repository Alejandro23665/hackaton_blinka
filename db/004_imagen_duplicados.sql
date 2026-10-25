-- Paso 4: imagen del documento y duplicados.

-- Dónde está guardado el archivo original (imagen o PDF) del que salió el documento:
-- el revisor lo ve para corregir los NO_LEGIBLE y DESCUADRE.
ALTER TABLE documentos_procesados ADD COLUMN imagen VARCHAR(255) NOT NULL;

-- El mismo documento (tipo, RUT y folio) no se guarda dos veces. No aplica al RUT ilegible (1-9):
-- documentos distintos pueden compartirlo.
CREATE UNIQUE INDEX uq_documentos_procesados_documento
    ON documentos_procesados (id_tipo_documento, rut_proveedor, folio)
    WHERE rut_proveedor <> '1-9';

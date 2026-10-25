-- Paso 2: tipos de documento y documentos procesados.

-- Solo tres tipos: factura electrónica, control interno y guía de despacho
CREATE TABLE tipos_documentos (
    id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    documento   VARCHAR(2) NOT NULL UNIQUE CHECK (documento IN ('FC', 'CI', 'GD')),
    descripcion VARCHAR(50) NOT NULL
);

INSERT INTO tipos_documentos (documento, descripcion) VALUES
    ('FC', 'Factura electrónica'),
    ('CI', 'Control interno'),
    ('GD', 'Guía de despacho');

-- Lo leído de cada documento. Montos en pesos chilenos (enteros, sin decimales).
-- Los datos que no se pudieron leer quedan vacíos (NULL).
CREATE TABLE documentos_procesados (
    id                INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rut_proveedor     VARCHAR(12),            -- sin puntos y con guion: 76084682-1
    folio             VARCHAR(20),            -- texto: conserva ceros a la izquierda (097938492)
    fecha             DATE,
    firma             BOOLEAN NOT NULL DEFAULT false,
    impuestos         BIGINT CHECK (impuestos >= 0),
    total_neto        BIGINT CHECK (total_neto >= 0),
    iva               BIGINT CHECK (iva >= 0),
    total             BIGINT CHECK (total >= 0),
    observaciones     VARCHAR(12) NOT NULL CHECK (observaciones IN ('LEGIBLE', 'NO_LEGIBLE')),
    id_tipo_documento INTEGER NOT NULL REFERENCES tipos_documentos (id) ON DELETE RESTRICT,
    creado_en         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_documentos_procesados_tipo ON documentos_procesados (id_tipo_documento);
CREATE INDEX ix_documentos_procesados_rut_folio ON documentos_procesados (rut_proveedor, folio);

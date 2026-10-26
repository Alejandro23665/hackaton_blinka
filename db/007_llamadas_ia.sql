-- Paso 7: una fila por cada solicitud pagada a la IA (las respuestas de la caché no se cobran ni se registran).
CREATE TABLE llamadas_ia (
    id             INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    creado_en      TIMESTAMPTZ NOT NULL DEFAULT now(),
    etapa          VARCHAR(14) NOT NULL CHECK (etapa IN ('CLASIFICACION', 'LECTURA_1', 'LECTURA_2')),
    modelo         VARCHAR(60) NOT NULL,
    id_tanda       VARCHAR(80),                       -- tanda de Message Batches; vacío en modo directo
    tokens_entrada INTEGER NOT NULL DEFAULT 0 CHECK (tokens_entrada >= 0),
    tokens_salida  INTEGER NOT NULL DEFAULT 0 CHECK (tokens_salida >= 0),  -- incluye el razonamiento
    costo_usd      NUMERIC(12, 6) NOT NULL DEFAULT 0 CHECK (costo_usd >= 0),
    espera_s       NUMERIC(10, 1) CHECK (espera_s >= 0),  -- cuánto tardó la tanda (o la llamada) en responder
    resultado      VARCHAR(8) NOT NULL CHECK (resultado IN ('OK', 'ERROR', 'RECHAZO', 'FORMATO')),
    id_documento   INTEGER REFERENCES documentos_procesados (id) ON DELETE SET NULL  -- vacío en la clasificación
);

CREATE INDEX ix_llamadas_ia_creado_en ON llamadas_ia (creado_en);
CREATE INDEX ix_llamadas_ia_documento ON llamadas_ia (id_documento);

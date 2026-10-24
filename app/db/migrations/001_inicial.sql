-- Migración inicial de la app de facturas.

-- `values` guarda lo que pidio el contador, un objeto por valor, con la FRASE
-- adentro. La frase es la clave del emparejamiento en el export: si solo se
-- guardara el valor con su posicion, reordenar plantilla.csv despues de
-- escanear haria que cada columna recibiera el valor de otra.
--
-- No hay campos de control ni deduplicacion: cada foto crea una fila, aunque
-- sea la misma foto enviada dos veces.
CREATE TABLE invoices (
    id            SERIAL PRIMARY KEY,
    review_status VARCHAR(20) NOT NULL DEFAULT 'needs_review',
    review_reason TEXT,
    values        JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- D-02: la imagen va en disco. Se guardan LAS DOS: la original tal como llego
-- del iPhone y la convertida, que es la que va al OCR.
-- D-01: el motor va solo aqui, en `ocr_runs.engine_version`; `invoices.values`
-- nunca guarda `engine`.
-- `raw_text` a veces es NULL: solo se guarda cuando algun valor salio dudoso o
-- no coincidio, que es cuando sirve para depurar.
CREATE TABLE ocr_runs (
    id             SERIAL PRIMARY KEY,
    invoice_id     INTEGER REFERENCES invoices(id) ON DELETE SET NULL,
    original_path  TEXT NOT NULL,
    converted_path TEXT,
    raw_text       TEXT,
    engine_version VARCHAR(80) NOT NULL,
    confidence     DOUBLE PRECISION,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indices solo donde hay filtro (SCHEMAS.md 7). Ninguno sobre el JSONB: los
-- valores del contador no se filtran, se exportan.
CREATE INDEX idx_invoices_review_status ON invoices(review_status);
CREATE INDEX idx_ocr_runs_invoice       ON ocr_runs(invoice_id);
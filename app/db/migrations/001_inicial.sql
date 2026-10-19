-- Migración inicial de la app de facturas.
-- Ver `specs/001-base-datos/design.md`. Las decisiones D-00 a D-03 están
-- resueltas: este archivo es definitivo y no se reescribe nunca.

CREATE TABLE fiscal_profiles (
    id            SERIAL PRIMARY KEY,
    country_code  VARCHAR(2)   NOT NULL UNIQUE,
    name          VARCHAR(80)  NOT NULL,
    currency      VARCHAR(3)   NOT NULL DEFAULT 'VES'
);

-- D-00: `values` guarda lo que pidio el contador, un objeto por valor, con la
-- FRASE adentro. La frase es la clave del emparejamiento en el export: si solo
-- se guardara el valor con su posicion, reordenar plantilla.csv despues de
-- escanear haria que cada columna recibiera el valor de otra.
--
-- `supplier_rif` acepta NULL a proposito (SCHEMAS.md 2.1): si no se pudo leer
-- el RIF, la factura se guarda igual y avisa con `unreadable_rif`.
CREATE TABLE invoices (
    id                 SERIAL PRIMARY KEY,
    supplier_rif       VARCHAR(20),
    serie              VARCHAR(20),
    numero             VARCHAR(40),
    issue_date         DATE,
    fiscal_profile_id  INTEGER REFERENCES fiscal_profiles(id),
    dedupe_key         TEXT NOT NULL UNIQUE,
    review_status      VARCHAR(20) NOT NULL DEFAULT 'needs_review',
    review_reason      TEXT,
    values             JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE invoice_items (
    id           SERIAL PRIMARY KEY,
    invoice_id   INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    line_number  INTEGER NOT NULL,
    code         VARCHAR(40),
    description  TEXT,
    quantity     DOUBLE PRECISION,
    unit_price   DOUBLE PRECISION,
    amount       DOUBLE PRECISION
);

CREATE TABLE taxes (
    id          SERIAL PRIMARY KEY,
    invoice_id  INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    item_id     INTEGER REFERENCES invoice_items(id) ON DELETE CASCADE,
    tax_type    VARCHAR(40) NOT NULL,
    rate        DOUBLE PRECISION,
    base_amount DOUBLE PRECISION,
    amount      DOUBLE PRECISION NOT NULL DEFAULT 0
);

-- D-02: la imagen va en disco. Se guardan LAS DOS: la original tal como llego
-- del iPhone y la convertida, que es la que va al OCR.
-- D-01: el motor va por valor dentro de `invoices.values`; aqui va el motor
-- PRINCIPAL de la foto, para saber con que se proceso.
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
CREATE INDEX idx_invoices_issue_date   ON invoices(issue_date);
CREATE INDEX idx_invoices_supplier_rif ON invoices(supplier_rif);
CREATE INDEX idx_invoice_items_invoice  ON invoice_items(invoice_id);
CREATE INDEX idx_taxes_invoice          ON taxes(invoice_id);
CREATE INDEX idx_ocr_runs_invoice       ON ocr_runs(invoice_id);
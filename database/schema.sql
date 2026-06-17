-- Schema PostGIS para escala corporativa — Case Sicredi SAC
-- Requer extensão PostGIS

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS properties (
    id VARCHAR(20) PRIMARY KEY,
    car_code VARCHAR(64) NOT NULL UNIQUE,
    uf CHAR(2) NOT NULL,
    label VARCHAR(255),
    area_ha NUMERIC(12, 4),
    geom GEOMETRY(MultiPolygon, 4326),
    source VARCHAR(100),
    source_confidence VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_properties_geom ON properties USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_properties_car ON properties (car_code);

CREATE TABLE IF NOT EXISTS source_layers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    theme VARCHAR(50) NOT NULL,
    source_url TEXT,
    download_date DATE,
    version VARCHAR(50),
    confidence VARCHAR(20),
    file_path TEXT,
    crs VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS evidence (
    id VARCHAR(50) PRIMARY KEY,
    property_id VARCHAR(20) REFERENCES properties(id),
    source_layer_id INTEGER REFERENCES source_layers(id),
    theme VARCHAR(50) NOT NULL,
    area_ha NUMERIC(12, 4),
    percent_of_property NUMERIC(8, 4),
    confidence VARCHAR(20),
    interpretation TEXT,
    limitation TEXT,
    geometry_operation VARCHAR(50) DEFAULT 'intersection',
    geom GEOMETRY(Geometry, 4326),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_evidence_property ON evidence (property_id);
CREATE INDEX IF NOT EXISTS idx_evidence_theme ON evidence (theme);

CREATE TABLE IF NOT EXISTS risk_scores (
    property_id VARCHAR(20) PRIMARY KEY REFERENCES properties(id),
    iesc_score NUMERIC(6, 2),
    risk_class VARCHAR(20),
    current_risk TEXT,
    prospective_risk TEXT,
    confidence VARCHAR(20),
    recommendation TEXT,
    main_drivers TEXT,
    calculated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS processing_runs (
    id SERIAL PRIMARY KEY,
    run_date TIMESTAMPTZ DEFAULT NOW(),
    script_version VARCHAR(20),
    source_snapshot JSONB,
    status VARCHAR(20) DEFAULT 'completed',
    properties_processed INTEGER,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    property_id VARCHAR(20) REFERENCES properties(id),
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20),
    message TEXT,
    evidence_id VARCHAR(50) REFERENCES evidence(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'open',
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_alerts_property ON alerts (property_id);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts (status);

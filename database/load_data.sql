-- Exemplo de carga a partir dos CSVs gerados pelo pipeline
-- Executar após schema.sql com dados em output/tables/

-- COPY properties FROM '/path/to/properties.csv' CSV HEADER;
-- Inserção via script Python com geoalchemy2 recomendada para geometrias

INSERT INTO processing_runs (script_version, status, notes)
VALUES ('1.0.0', 'completed', 'Carga inicial case Sicredi');

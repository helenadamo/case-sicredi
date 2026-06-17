-- Views analíticas para dashboard SAC

CREATE OR REPLACE VIEW vw_property_risk AS
SELECT
    p.id,
    p.car_code,
    p.uf,
    p.label,
    p.area_ha,
    r.iesc_score,
    r.risk_class,
    r.current_risk,
    r.prospective_risk,
    r.confidence AS evidence_confidence,
    r.recommendation,
    r.main_drivers
FROM properties p
LEFT JOIN risk_scores r ON p.id = r.property_id;

CREATE OR REPLACE VIEW vw_evidence_summary AS
SELECT
    e.property_id,
    e.theme,
    COUNT(*) AS evidence_count,
    SUM(e.area_ha) AS total_area_ha,
    MAX(e.percent_of_property) AS max_percent,
    MIN(e.confidence) AS min_confidence
FROM evidence e
GROUP BY e.property_id, e.theme;

CREATE OR REPLACE VIEW vw_open_alerts AS
SELECT
    a.*,
    p.car_code,
    p.uf
FROM alerts a
JOIN properties p ON a.property_id = p.id
WHERE a.status = 'open';

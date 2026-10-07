-- The grain of near_dive_site_occurrences is one row per (occurrence_key, site_id), both set.
-- A duplicate pair means the join fanned out (duplicate site_id or occurrence_key upstream).

SELECT
    occurrence_key,
    site_id,
    COUNT(*) AS n
FROM {{ ref('near_dive_site_occurrences') }}
GROUP BY occurrence_key, site_id
HAVING COUNT(*) > 1
    OR occurrence_key IS NULL
    OR site_id IS NULL

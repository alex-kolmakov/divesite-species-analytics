-- The divesite_summary species counts must match the divesite_species rows the site list shows
-- (birds excluded). If these diverge, the summary table is stale or the aggregation is wrong.
-- The UI relies on summary counts matching what the site panel shows.

SELECT
    ds.site_id,
    ds.total_species AS summary_count,
    COALESCE(detail.actual_count, 0) AS actual_count
FROM {{ ref('divesite_summary') }} AS ds
LEFT JOIN (
    SELECT site_id, COUNT(DISTINCT species) AS actual_count
    FROM {{ ref('divesite_species') }}
    WHERE NOT is_bird
    GROUP BY site_id
) AS detail ON ds.site_id = detail.site_id
WHERE ds.total_species != COALESCE(detail.actual_count, 0)

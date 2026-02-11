-- The divesite_summary species counts must match the actual detail rows.
-- If these diverge, the summary table is stale or the aggregation is wrong.
-- The UI relies on summary counts matching what the detail panel shows.

SELECT
    ds.dive_site,
    ds.total_species AS summary_count,
    detail.actual_count
FROM {{ ref('divesite_summary') }} AS ds
INNER JOIN (
    SELECT dive_site, COUNT(DISTINCT species) AS actual_count
    FROM {{ ref('divesite_species_detail') }}
    GROUP BY dive_site
) AS detail ON ds.dive_site = detail.dive_site
WHERE ds.total_species != detail.actual_count

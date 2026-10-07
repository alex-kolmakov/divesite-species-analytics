-- Every site with species on its list has a rank-1 species, and only birds have no rank.
-- Catches a per-site ranking that still counts the hidden birds or drops a site.

SELECT site_id, 'no rank 1' AS failure_reason
FROM {{ ref('divesite_species') }}
WHERE NOT is_bird
GROUP BY site_id
HAVING MIN(frequency_rank) != 1
UNION ALL
SELECT site_id, 'rank on a bird or missing rank' AS failure_reason
FROM {{ ref('divesite_species') }}
WHERE (is_bird AND frequency_rank IS NOT NULL) OR (NOT is_bird AND frequency_rank IS NULL)
GROUP BY site_id

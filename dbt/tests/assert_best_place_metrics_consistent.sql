-- The per-site metrics nest: a recent day is a day, a day has at least one record, and a species
-- seen at all has a positive score and dates in order. A break means the daily rollup is wrong.
-- Every species also needs exactly one best place (rank 1), ties aside.

SELECT
    site_id,
    species,
    'metrics out of order' AS failure_reason
FROM {{ ref('divesite_species_frequency') }}
WHERE days_seen_recent > days_seen
   OR days_seen > sighting_count
   OR days_seen < 1
   OR best_place_score <= 0
   OR best_place_score > days_seen
   OR first_seen > last_seen
   OR ARRAY_LENGTH(months_seen) NOT BETWEEN 1 AND 12

UNION ALL

SELECT
    CAST(NULL AS STRING) AS site_id,
    species,
    'no best place' AS failure_reason
FROM {{ ref('divesite_species_frequency') }}
GROUP BY species
HAVING MIN(best_place_rank) != 1

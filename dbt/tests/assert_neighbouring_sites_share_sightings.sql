-- A sighting counts for every dive site within PROXIMITY_METERS. So if an occurrence is x metres
-- from a site, and that site's nearest neighbour is g metres away, the occurrence is at most
-- x + g from the neighbour (triangle inequality): when x + g fits in the radius, the pair with the
-- neighbour must exist too. A missing pair means the join dropped rows (the old ranking kept one
-- site per timestamp, so neighbouring sites could never share a sighting).
--
-- Unlike assert_near_matches_naive_recount this needs no sample and never reads occurrences: it
-- covers every month and every site that has a neighbour in range. The 1 m margin absorbs
-- floating-point noise in the distances.

{% set radius = env_var('PROXIMITY_METERS') %}

WITH nearest_neighbour AS (
    SELECT
        site.site_id,
        other.site_id AS neighbour_id,
        ST_DISTANCE(site.geography, other.geography) AS gap_m
    FROM {{ ref('divesites') }} AS site
    INNER JOIN {{ ref('divesites') }} AS other
        ON ST_DWITHIN(site.geography, other.geography, {{ radius }})
        AND site.site_id != other.site_id
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY site.site_id
        ORDER BY ST_DISTANCE(site.geography, other.geography), other.site_id
    ) = 1
)

SELECT
    mine.occurrence_key,
    mine.site_id,
    nn.neighbour_id,
    mine.distance_m,
    nn.gap_m
FROM {{ ref('near_dive_site_occurrences') }} AS mine
INNER JOIN nearest_neighbour AS nn
    ON mine.site_id = nn.site_id
LEFT JOIN {{ ref('near_dive_site_occurrences') }} AS theirs
    ON theirs.site_id = nn.neighbour_id
    AND theirs.occurrence_key = mine.occurrence_key
WHERE mine.distance_m + nn.gap_m <= {{ radius }} - 1
  AND theirs.occurrence_key IS NULL

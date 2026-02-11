-- Distance between an occurrence and its matched dive site must be >= 0.

SELECT *
FROM {{ ref('near_dive_site_occurrences') }}
WHERE distance_to_dive_site < 0

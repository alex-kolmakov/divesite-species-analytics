-- Every matched occurrence should be within the configured proximity radius.
-- If this fails, ST_DWithin filtering is not working as expected.

SELECT *
FROM {{ ref('near_dive_site_occurrences') }}
WHERE distance_m > {{ env_var('PROXIMITY_METERS') }}
   OR distance_m IS NULL

-- Every matched occurrence should be within the configured proximity radius.
-- If this fails, ST_DWithin filtering is not working as expected.

SELECT *
FROM {{ ref('near_dive_site_occurrences') }}
WHERE distance_to_dive_site > {{ env_var('PROXIMITY_METERS') }}

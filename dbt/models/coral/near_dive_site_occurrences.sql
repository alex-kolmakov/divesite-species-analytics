{{ config(materialized='table', cluster_by=['site_id', 'species']) }}

-- One row per (occurrence_key, site_id) within PROXIMITY_METERS. A sighting counts for every dive
-- site in range: the question is "what lives at this site", not "which single site owns this
-- record". So rows here outnumber occurrences near sites, and occurrence-level totals must come
-- from occurrences, never from summing this table across sites.
--
-- This is the only coral model that reads occurrences; everything downstream reads this table.

{% if env_var("DEVELOPMENT", "false") == "true" %}
-- In dev, subsample to a representative set of species to keep the result small
WITH sampled_occurrences AS (
    SELECT *
    FROM {{ ref('occurrences') }}
    WHERE MOD(FARM_FINGERPRINT(species), 20) = 0
)
{% else %}
WITH sampled_occurrences AS (
    SELECT *
    FROM {{ ref('occurrences') }}
)
{% endif %}

SELECT
    occ.occurrence_key,
    divesites.site_id,
    occ.species,
    occ.event_date,
    occ.individual_count,
    occ.source,
    ST_DISTANCE(occ.geography, divesites.geography) AS distance_m
FROM sampled_occurrences AS occ
INNER JOIN {{ ref('divesites') }} AS divesites
    ON ST_DWITHIN(
        occ.geography,
        divesites.geography,
        {{ env_var('PROXIMITY_METERS') }}
    )

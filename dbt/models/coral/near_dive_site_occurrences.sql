{{ config(materialized='table') }}

{% if env_var("DEVELOPMENT", "false") == "true" %}
-- In dev, subsample to a representative set of species to reduce CROSS JOIN cost
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
    divesites.title AS dive_site,
    occ.event_date,
    occ.species,
    occ.individual_count,
    ST_Distance(occ.geography, divesites.geography) AS distance_to_dive_site,
    occ.geography,
    occ.source,
    ROW_NUMBER() OVER (
        PARTITION BY occ.event_date
        ORDER BY ST_Distance(occ.geography, divesites.geography)
    ) AS proximity_rank
FROM sampled_occurrences AS occ
CROSS JOIN {{ ref('divesites') }} AS divesites
WHERE ST_DWithin(
    occ.geography,
    divesites.geography,
    {{ env_var('PROXIMITY_METERS') }}
)
QUALIFY proximity_rank = 1
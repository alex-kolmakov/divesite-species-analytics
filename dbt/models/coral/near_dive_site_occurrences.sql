{{ config(materialized='table') }}

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
FROM {{ ref('occurrences') }} AS occ
CROSS JOIN {{ ref('divesites') }} AS divesites
WHERE ST_DWithin(
    occ.geography, 
    divesites.geography, 
    {{ env_var('PROXIMITY_METERS') }}
)
QUALIFY proximity_rank = 1
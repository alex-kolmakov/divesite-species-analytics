{{ config(materialized='table') }}

WITH dive_site_redlist_occurrences AS (
    SELECT 
        divesites.title,  
        occurences.eventdate,
        occurences.species,
        occurences.individualcount,
        ST_Distance(occurences.geography,  divesites.geography) AS distance_to_dive_site,
        ROW_NUMBER() OVER (PARTITION BY occurences.eventdate ORDER BY ST_Distance(occurences.geography, divesites.geography)) as proximity_rank,
        occurences.geography,
        occurences.source,
        occurences.is_endangered,
        occurences.is_invasive
    FROM {{ ref('occurences') }} AS occurences
    CROSS JOIN {{ ref('divesites') }} AS divesites
    WHERE ST_DWithin(occurences.geography, divesites.geography, {{ env_var('PROXIMITY_METERS') }}) 
    AND occurences.eventdate >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {{ env_var('AGGREGATION_WINDOW_DAYS') }} DAY)
)

SELECT *
FROM dive_site_redlist_occurrences
WHERE proximity_rank = 1

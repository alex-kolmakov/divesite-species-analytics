{{ config(materialized='table') }}

WITH counts AS (
    SELECT
        dive_site,
        species,
        event_date,
        FORMAT_DATE('%b', event_date) AS month,
        COUNT(*) AS sighting_count
    FROM {{ ref('near_dive_site_occurrences') }} AS occ
    GROUP BY 
        dive_site,
        species,
        event_date,
        month
)
SELECT
    counts.dive_site,
    counts.species,
    divesites.geography,
    counts.month,
    counts.event_date,
    counts.sighting_count
FROM counts
INNER JOIN {{ ref('divesites') }} AS divesites
    ON counts.dive_site = divesites.title
ORDER BY
    counts.dive_site,
    counts.species,
    counts.month
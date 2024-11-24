{{ config(materialized='table') }}

WITH species_counts AS (
    SELECT
        dive_site,
        species,
        COUNT(*) AS sighting_count
    FROM {{ ref('near_dive_site_occurrences') }}
    GROUP BY 
        dive_site,
        species
),

species_rankings AS (
    SELECT
        *,
        RANK() OVER (
            PARTITION BY dive_site 
            ORDER BY sighting_count DESC
        ) AS frequency_rank
    FROM species_counts
)

SELECT * FROM species_rankings
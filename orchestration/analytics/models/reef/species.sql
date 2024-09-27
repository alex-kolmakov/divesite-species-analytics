{{ config(materialized='table') }}

WITH unique_species AS (
    SELECT DISTINCT species
    FROM {{ ref('near_divesite_occurrences') }}
    WHERE species IS NOT NULL
)

SELECT
    spec.species,
    IF(redlist.scientificName IS NOT NULL, TRUE, FALSE) AS is_endangered,
    IF(invasive.scientificName IS NOT NULL, TRUE, FALSE) AS is_invasive,
    CASE
        WHEN redlist.scientificName IS NOT NULL THEN 'endangered'
        WHEN invasive.scientificName IS NOT NULL THEN 'invasive'
        ELSE 'normal'
    END AS species_type
FROM unique_species AS spec
LEFT JOIN {{ source('marine_data', 'redlist_table') }} AS redlist
    ON spec.species = redlist.scientificName
LEFT JOIN {{ source('marine_data', 'invasive_table') }} AS invasive
    ON spec.species = invasive.scientificName
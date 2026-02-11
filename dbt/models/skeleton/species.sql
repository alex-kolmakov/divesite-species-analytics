{{ config(
    materialized='table')
}}

WITH unique_species AS (
    SELECT DISTINCT species
    FROM {{ ref('clustered_occurrences') }}
)

SELECT
    spec.species,
    IF(redlist.scientificName IS NOT NULL, TRUE, FALSE) AS is_endangered,
    IF(invasive.scientificName IS NOT NULL, TRUE, FALSE) AS is_invasive,
    CASE
        WHEN redlist.scientificName IS NOT NULL THEN 'endangered'
        WHEN invasive.scientificName IS NOT NULL THEN 'invasive'
        ELSE 'normal'
    END AS species_type,
    CAST(null AS STRING) AS common_name,
    CAST(null AS STRING) AS description,
    CAST(null AS STRING) AS image_url
FROM unique_species AS spec
LEFT JOIN (
    SELECT DISTINCT scientificName FROM {{ source('marine_data', 'redlist_table') }}
) AS redlist
    ON spec.species = redlist.scientificName
LEFT JOIN (
    SELECT DISTINCT scientificName FROM {{ source('marine_data', 'invasive_table') }}
) AS invasive
    ON spec.species = invasive.scientificName
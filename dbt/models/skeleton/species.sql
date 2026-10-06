{{ config(materialized='table') }}

WITH unique_species AS (
    SELECT DISTINCT species
    FROM {{ ref('occurrences') }}
)

-- Red List names carry the author, so the match is on canonicalName (genus + epithet). Only the
-- threatened categories (VU, EN, CR) count as endangered; the list also holds Least Concern.
SELECT
    spec.species,
    redlist.threatStatus AS iucn_category,
    COALESCE(redlist.is_threatened, FALSE) AS is_endangered,
    IF(invasive.scientificName IS NOT NULL, TRUE, FALSE) AS is_invasive,
    CASE
        WHEN redlist.is_threatened THEN 'endangered'
        WHEN invasive.scientificName IS NOT NULL THEN 'invasive'
        ELSE 'normal'
    END AS species_type
FROM unique_species AS spec
LEFT JOIN (
    SELECT
        canonicalName,
        ANY_VALUE(threatStatus) AS threatStatus,
        LOGICAL_OR(threatStatus IN ('vulnerable', 'endangered', 'critically endangered')) AS is_threatened
    FROM {{ source('marine_data', 'redlist_table') }}
    WHERE canonicalName IS NOT NULL
    GROUP BY canonicalName
) AS redlist
    ON spec.species = redlist.canonicalName
LEFT JOIN (
    SELECT DISTINCT scientificName FROM {{ source('marine_data', 'invasive_table') }}
) AS invasive
    ON spec.species = invasive.scientificName
{{ config(materialized='table') }}

WITH unique_species AS (
    SELECT DISTINCT species
    FROM {{ ref('occurrences') }}
)

-- Red List names carry the author, so the match is on canonicalName (genus + epithet). Only the
-- threatened categories (VU, EN, CR) count as endangered; the list also holds Least Concern.
-- is_invasive means "invasive somewhere" (WRiMS): whether it is invasive at a given dive site is
-- in divesite_invasive_species, since the same species can be native elsewhere.
-- taxon_class comes from WoRMS (the accepted name's row first); it is how birds (Aves), which WoRMS
-- lists as marine, are kept out of the per-site lists.
SELECT
    spec.species,
    taxonomy.taxon_class,
    redlist.threatStatus AS iucn_category,
    COALESCE(redlist.is_threatened, FALSE) AS is_endangered,
    invasive.species IS NOT NULL AS is_invasive,
    CASE
        WHEN redlist.is_threatened THEN 'endangered'
        WHEN invasive.species IS NOT NULL THEN 'invasive'
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
    SELECT DISTINCT species FROM {{ source('marine_data', 'wrims_table') }}
    WHERE invasiveness = 'Invasive'
) AS invasive
    ON spec.species = invasive.species
LEFT JOIN (
    SELECT
        scientificName,
        ARRAY_AGG(`class` IGNORE NULLS ORDER BY taxonomicStatus = 'accepted' DESC LIMIT 1)[SAFE_OFFSET(0)] AS taxon_class
    FROM {{ source('marine_data', 'worms_table') }}
    GROUP BY scientificName
) AS taxonomy
    ON spec.species = taxonomy.scientificName
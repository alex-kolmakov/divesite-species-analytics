{{ config(materialized='table') }}

WITH unique_species AS (
    SELECT DISTINCT species
    FROM {{ ref('occurrences') }}
)

-- Red List names carry the author, so the match is on canonicalName (genus + epithet). Only the
-- threatened categories (VU, EN, CR) count as endangered; the list also holds Least Concern.
-- is_invasive means "invasive somewhere" (WRiMS): whether it is invasive at a given dive site is
-- in divesite_invasive_species, since the same species can be native elsewhere.
-- is_above_water marks what WoRMS lists but a diver doesn't meet underwater: birds, insects, spiders
-- and mites, fungi and lichens, and land plants (shore grasses, rushes, mangroves). Seagrasses and
-- pondweeds grow submerged and stay. These species are left out of site lists and counts, and keep
-- their own species pages. It is a rule on taxonomy, not habitat: the WoRMS marine / freshwater /
-- terrestrial flags aren't ingested.
-- taxon_class comes from WoRMS (the accepted name's row first); it is how birds (Aves), which WoRMS
-- lists as marine, are kept out of the per-site lists.
SELECT
    spec.species,
    taxonomy.taxon_class,
    COALESCE(
        taxonomy.taxon_class IN ('Aves', 'Insecta', 'Arachnida')
        OR taxonomy.kingdom = 'Fungi'
        OR (
            taxonomy.phylum IN ('Tracheophyta', 'Bryophyta')
            AND COALESCE(taxonomy.family, '') NOT IN (
                'Zosteraceae', 'Posidoniaceae', 'Cymodoceaceae', 'Hydrocharitaceae', 'Ruppiaceae', 'Potamogetonaceae'
            )
        ),
        FALSE
    ) AS is_above_water,
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
        ARRAY_AGG(kingdom IGNORE NULLS ORDER BY taxonomicStatus = 'accepted' DESC LIMIT 1)[SAFE_OFFSET(0)] AS kingdom,
        ARRAY_AGG(phylum IGNORE NULLS ORDER BY taxonomicStatus = 'accepted' DESC LIMIT 1)[SAFE_OFFSET(0)] AS phylum,
        ARRAY_AGG(`class` IGNORE NULLS ORDER BY taxonomicStatus = 'accepted' DESC LIMIT 1)[SAFE_OFFSET(0)] AS taxon_class,
        ARRAY_AGG(family IGNORE NULLS ORDER BY taxonomicStatus = 'accepted' DESC LIMIT 1)[SAFE_OFFSET(0)] AS family
    FROM {{ source('marine_data', 'worms_table') }}
    GROUP BY scientificName
) AS taxonomy
    ON spec.species = taxonomy.scientificName
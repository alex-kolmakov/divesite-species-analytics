{{ config(materialized='table') }}

-- App table: one row per species recorded at a dive site, with its descriptive fields and labels.
-- is_invasive / species_type are species-level ("invasive somewhere"); where it is invasive is
-- per site in divesite_species. iucn_category is the global Red List category.

SELECT
    sp.species,
    sp.taxon_class,
    enrich.common_name,
    enrich.description,
    enrich.description_is_stub,
    enrich.image_url,
    -- Credit for the image: show image_credit (or "via Wikimedia Commons" when empty) and license,
    -- linking to image_page_url
    enrich.image_credit,
    enrich.image_license,
    enrich.image_license_url,
    enrich.image_page_url,
    enrich.image_source,
    sp.iucn_category,
    sp.is_endangered,
    sp.is_invasive,
    sp.species_type,
    agg.total_sites,
    agg.invasive_sites,
    agg.recent_sites,
    agg.last_seen
FROM (
    SELECT
        species,
        COUNT(*)                     AS total_sites,
        COUNTIF(is_invasive_here)    AS invasive_sites,
        COUNTIF(days_seen_recent > 0) AS recent_sites,
        MAX(last_seen)               AS last_seen
    FROM {{ ref('divesite_species') }}
    GROUP BY species
) AS agg
INNER JOIN {{ ref('species') }} AS sp ON agg.species = sp.species
LEFT JOIN {{ source('marine_data', 'species_enrichment') }} AS enrich ON agg.species = enrich.species

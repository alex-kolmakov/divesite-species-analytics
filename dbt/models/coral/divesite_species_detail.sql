{{ config(materialized='table', cluster_by=['dive_site']) }}

SELECT
    freq.dive_site,
    ST_Y(ds.geography) AS dive_site_latitude,
    ST_X(ds.geography) AS dive_site_longitude,
    freq.species,
    enrich.common_name,
    enrich.description,
    enrich.image_url,
    sp.is_endangered,
    sp.is_invasive,
    sp.species_type,
    freq.sighting_count,
    freq.frequency_rank
FROM {{ ref('divesite_species_frequency') }} AS freq
INNER JOIN {{ ref('species') }} AS sp ON freq.species = sp.species
INNER JOIN {{ ref('divesites') }} AS ds ON freq.dive_site = ds.title
LEFT JOIN {{ source('marine_data', 'species_enrichment') }} AS enrich ON freq.species = enrich.species

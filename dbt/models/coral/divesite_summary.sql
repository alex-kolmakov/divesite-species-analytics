{{ config(materialized='table') }}

SELECT
    ds.title           AS dive_site,
    ST_Y(ds.geography) AS latitude,
    ST_X(ds.geography) AS longitude,
    ds.country_iso3,
    ds.avg_max_depth,
    ds.avg_divetime,
    ds.avg_visibility,
    ds.avg_rating,
    ds.logged_dives,
    ds.site_source,
    COALESCE(agg.total_species,    0) AS total_species,
    COALESCE(agg.total_sightings,  0) AS total_sightings,
    COALESCE(agg.endangered_count, 0) AS endangered_count,
    COALESCE(agg.invasive_count,   0) AS invasive_count
FROM {{ ref('divesites') }} AS ds
LEFT JOIN (
    SELECT
        dive_site,
        COUNT(DISTINCT species)  AS total_species,
        SUM(sighting_count)      AS total_sightings,
        COUNTIF(is_endangered)   AS endangered_count,
        COUNTIF(is_invasive)     AS invasive_count
    FROM {{ ref('divesite_species_detail') }}
    GROUP BY dive_site
) AS agg ON ds.title = agg.dive_site

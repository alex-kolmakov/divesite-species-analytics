{{ config(materialized='table') }}

SELECT
    ds.site_id,
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
    COALESCE(agg.recent_species,   0) AS recent_species,
    COALESCE(agg.total_sightings,  0) AS total_sightings,
    COALESCE(agg.endangered_count, 0) AS endangered_count,
    COALESCE(agg.invasive_count,   0) AS invasive_count,
    agg.last_seen
FROM {{ ref('divesites') }} AS ds
LEFT JOIN (
    SELECT
        dsp.site_id,
        COUNT(*)                          AS total_species,
        COUNTIF(dsp.days_seen_recent > 0) AS recent_species,
        SUM(dsp.sighting_count)           AS total_sightings,
        COUNTIF(sp.is_endangered)         AS endangered_count,
        COUNTIF(dsp.is_invasive_here)     AS invasive_count,
        MAX(dsp.last_seen)                AS last_seen
    FROM {{ ref('divesite_species') }} AS dsp
    INNER JOIN {{ ref('species') }} AS sp ON dsp.species = sp.species
    WHERE NOT dsp.is_above_water
    GROUP BY dsp.site_id
) AS agg ON ds.site_id = agg.site_id

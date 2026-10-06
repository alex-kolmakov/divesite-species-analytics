{{ config(
    materialized='table',
    partition_by={
        "field": "event_date",
        "data_type": "timestamp",
        "granularity": "month"
    },
    cluster_by=['geography']
)}}

{% set proximity_meters = env_var('PROXIMITY_METERS') %}
{% set min_year = env_var('MIN_YEAR', '1900') %}

-- Every quality rule lives here, over the staged GBIF/OBIS copies, so rebuilding this model never
-- scans GBIF or the OBIS parquet. analyses/occurrence_filter_counts.sql counts what each rule removes.
--
-- A record is kept when it is:
--   * a presence: not GBIF occurrenceStatus ABSENT, not OBIS absence, not a count <= 0
--     (0 = looked and found none; OBIS also uses -999 / -9 as "unknown" sentinels)
--   * not rejected by OBIS QC (dropped: on land, not marine, ...)
--   * not a fossil or a living (aquarium) specimen
--   * dated by a validated date between MIN_YEAR and now
--   * located: not 0/0, and known to within PROXIMITY_METERS (null uncertainty is accepted)
-- Missing counts stay null instead of being coerced to 1. OBIS counts are free text: "0.0" is a
-- zero, and fractions (".25", "0.000016") are densities, so they keep the record but not a count.

WITH gbif AS (
    SELECT
        CONCAT('gbif:', gbif_id)        AS occurrence_key,
        'GBIF'                          AS source,
        species,
        CAST(individualcount AS FLOAT64) AS count_value,
        eventdate                       AS event_date,
        decimallongitude                AS longitude,
        decimallatitude                 AS latitude,
        coordinate_uncertainty_m,
        basis_of_record
    FROM {{ ref('gbif_occurrences') }}
    WHERE occurrence_status IS DISTINCT FROM 'ABSENT'
),

obis AS (
    SELECT
        CONCAT('obis:', obis_id)        AS occurrence_key,
        'OBIS'                          AS source,
        species,
        SAFE_CAST(individualcount AS FLOAT64) AS count_value,
        TIMESTAMP_MILLIS(date_mid)      AS event_date,
        decimallongitude                AS longitude,
        decimallatitude                 AS latitude,
        coordinate_uncertainty_m,
        basis_of_record
    FROM {{ ref('obis_occurrences') }}
    WHERE absence IS NOT TRUE
      AND dropped IS NOT TRUE
),

filtered AS (
    SELECT *
    FROM (SELECT * FROM gbif UNION ALL SELECT * FROM obis)
    WHERE event_date IS NOT NULL
      AND EXTRACT(YEAR FROM event_date) >= {{ min_year }}
      AND event_date <= CURRENT_TIMESTAMP()
      AND longitude IS NOT NULL
      AND latitude IS NOT NULL
      AND NOT (longitude = 0 AND latitude = 0)
      AND (coordinate_uncertainty_m IS NULL OR coordinate_uncertainty_m <= {{ proximity_meters }})
      AND (count_value IS NULL OR count_value > 0)
      -- 'FOSSIL_SPECIMEN' (GBIF) and 'FossilSpecimen' (OBIS) both normalise to 'fossilspecimen'
      AND COALESCE(REGEXP_REPLACE(LOWER(basis_of_record), r'[^a-z]', ''), '')
          NOT IN ('fossilspecimen', 'livingspecimen')
),

-- Many OBIS datasets are also published through GBIF. A GBIF record is dropped as a copy when an
-- OBIS record has the same species, day and location (to ~11 m). Records within one source are
-- never merged: two observers can log the same species at the same spot on the same day.
-- Coordinates become INT64 grid keys: BigQuery forbids FLOAT64 in PARTITION BY.
deduped AS (
    SELECT *
    FROM filtered
    QUALIFY source = 'OBIS'
        OR COUNTIF(source = 'OBIS') OVER (
            PARTITION BY
                species,
                DATE(event_date),
                CAST(ROUND(latitude * 10000) AS INT64),
                CAST(ROUND(longitude * 10000) AS INT64)
        ) = 0
)

SELECT
    occurrence_key,
    source,
    species,
    IF(count_value = TRUNC(count_value), CAST(count_value AS INT64), NULL) AS individual_count,
    event_date,
    ST_GEOGPOINT(longitude, latitude) AS geography,
    coordinate_uncertainty_m,
    basis_of_record
FROM deduped

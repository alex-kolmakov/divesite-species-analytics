-- Rows removed by each rule in models/skeleton/occurrences.sql, per source.
-- Reads only the staged copies (no GBIF or OBIS parquet scan), ~60 GiB.
-- Run: dbt compile --select occurrence_filter_counts, then run target/compiled/.../occurrence_filter_counts.sql with bq.
-- A row is counted under the first rule that removes it, in the order below.

{% set proximity_meters = env_var('PROXIMITY_METERS') %}
{% set min_year = env_var('MIN_YEAR', '1900') %}

WITH staged AS (
    SELECT
        'GBIF' AS source,
        occurrence_status = 'ABSENT' AS is_absence,
        FALSE AS is_dropped,
        CAST(individualcount AS FLOAT64) AS count_value,
        eventdate AS event_date,
        decimallongitude AS longitude,
        decimallatitude AS latitude,
        coordinate_uncertainty_m,
        basis_of_record
    FROM {{ ref('gbif_occurrences') }}
    UNION ALL
    SELECT
        'OBIS',
        absence IS TRUE,
        dropped IS TRUE,
        SAFE_CAST(individualcount AS FLOAT64),
        TIMESTAMP_MILLIS(date_mid),
        decimallongitude,
        decimallatitude,
        coordinate_uncertainty_m,
        basis_of_record
    FROM {{ ref('obis_occurrences') }}
),

classified AS (
    SELECT
        source,
        CASE
            WHEN is_absence THEN '1 absence'
            WHEN is_dropped THEN '2 OBIS QC dropped'
            WHEN count_value <= 0 THEN '3 count <= 0'
            WHEN event_date IS NULL THEN '4 no valid date'
            WHEN EXTRACT(YEAR FROM event_date) < {{ min_year }} THEN '5 before MIN_YEAR'
            WHEN event_date > CURRENT_TIMESTAMP() THEN '6 future date'
            WHEN longitude IS NULL OR latitude IS NULL THEN '7 no coordinates'
            WHEN longitude = 0 AND latitude = 0 THEN '8 0/0 coordinates'
            WHEN coordinate_uncertainty_m > {{ proximity_meters }} THEN '9 uncertainty > radius'
            WHEN REGEXP_REPLACE(LOWER(basis_of_record), r'[^a-z]', '') IN ('fossilspecimen', 'livingspecimen')
                THEN '10 fossil / living specimen'
            ELSE '11 kept (before cross-source dedup)'
        END AS rule
    FROM staged
)

SELECT rule, source, COUNT(*) AS rows_
FROM classified
GROUP BY ALL
ORDER BY CAST(SPLIT(rule, ' ')[OFFSET(0)] AS INT64), source

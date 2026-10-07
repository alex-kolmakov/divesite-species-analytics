{{ config(materialized='table', cluster_by=['site_id']) }}

-- One row per (site_id, species, calendar month). `month` alone folds every year together
-- (seasonality); `month_start` keeps the year (trend).

WITH counts AS (
    SELECT
        site_id,
        species,
        DATE_TRUNC(DATE(event_date), MONTH) AS month_start,
        COUNT(*) AS sighting_count
    FROM {{ ref('near_dive_site_occurrences') }}
    GROUP BY
        site_id,
        species,
        month_start
)

SELECT
    counts.site_id,
    divesites.title AS dive_site,
    counts.species,
    divesites.geography,
    counts.month_start,
    EXTRACT(YEAR FROM counts.month_start)  AS year,
    EXTRACT(MONTH FROM counts.month_start) AS month,
    counts.sighting_count
FROM counts
INNER JOIN {{ ref('divesites') }} AS divesites
    ON counts.site_id = divesites.site_id

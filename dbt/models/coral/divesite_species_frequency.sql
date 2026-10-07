{{ config(materialized='table', cluster_by=['site_id']) }}

{% set half_life_years = env_var('BEST_PLACE_HALF_LIFE_YEARS', '3') %}
{% set recent_years = env_var('RECENT_YEARS', '5') %}

-- One row per (site_id, species) with how often and how recently the species was seen there.
--
-- sighting_count counts records, so one survey that logs a species a hundred times outweighs a
-- hundred divers on a hundred days. days_seen counts distinct days instead, and best_place_score
-- weights each day by its age: a day counts 1 today, 1/2 after BEST_PLACE_HALF_LIFE_YEARS, 1/4
-- after twice that. A site with hundreds of days ten years ago ranks below one seen often lately.
-- The score is relative to the build date, so it shifts a little with every rebuild.
--
-- Records dated only to a month or a year (OBIS date_mid) count as one day each.

WITH daily AS (
    SELECT
        site_id,
        species,
        DATE(event_date) AS day,
        COUNT(*) AS sightings
    FROM {{ ref('near_dive_site_occurrences') }}
    GROUP BY
        site_id,
        species,
        day
),

per_site_species AS (
    SELECT
        site_id,
        species,
        SUM(sightings) AS sighting_count,
        COUNT(*) AS days_seen,
        COUNTIF(day >= DATE_SUB(CURRENT_DATE(), INTERVAL {{ recent_years }} YEAR)) AS days_seen_recent,
        MIN(day) AS first_seen,
        MAX(day) AS last_seen,
        ARRAY_AGG(DISTINCT EXTRACT(MONTH FROM day) ORDER BY EXTRACT(MONTH FROM day)) AS months_seen,
        SUM(POW(0.5, DATE_DIFF(CURRENT_DATE(), day, DAY) / (365.25 * {{ half_life_years }}))) AS best_place_score
    FROM daily
    GROUP BY
        site_id,
        species
)

SELECT
    *,
    -- Most recorded species at the site (1 = most records)
    RANK() OVER (
        PARTITION BY site_id
        ORDER BY sighting_count DESC
    ) AS frequency_rank,
    -- Best sites to see the species (1 = most days seen, weighted by recency)
    RANK() OVER (
        PARTITION BY species
        ORDER BY best_place_score DESC
    ) AS best_place_rank
FROM per_site_species

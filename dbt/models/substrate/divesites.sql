{{ config(enabled=true, materialized='table', cluster_by=['geography']) }}

-- SSI is the primary dive site source (~10,600 sites, community-validated).
-- PADI supplements with ~2,700 locations not present in SSI.
--
-- Every site keeps its source ID as `site_id` ('ssi:<id>' / 'padi:<id>'): titles are not
-- unique ("Aquarium" x22, "Blue Hole" x13), so nothing downstream should key on them.
--
-- Deduplication is cross-source only: a PADI site is dropped when an SSI site is
--   * within 500 m and has a matching name (same normalised name, one contains the other,
--     or edit-distance similarity >= 0.8), or
--   * within 25 m whatever the name (same entry point; the 3 km species answer is identical).
-- Sites within one source are never merged: they have distinct IDs, and the old 0.001° grid
-- dedup silently dropped ~180 genuinely different sites that shared a cell.

WITH ssi AS (
    SELECT
        CONCAT('ssi:', CAST(id AS STRING))          AS site_id,
        name                                        AS title,
        SAFE_CAST(lat AS FLOAT64)                   AS latitude,
        SAFE_CAST(lng AS FLOAT64)                   AS longitude,
        country_iso3,
        SAFE_CAST(averageMaxDepth  AS FLOAT64)      AS avg_max_depth,
        SAFE_CAST(averageDivetime  AS FLOAT64)      AS avg_divetime,
        SAFE_CAST(averageVis       AS FLOAT64)      AS avg_visibility,
        SAFE_CAST(averageRating    AS FLOAT64)      AS avg_rating,
        SAFE_CAST(loggedDives      AS INT64)        AS logged_dives,
        'ssi'                                       AS site_source
    FROM {{ source('marine_data', 'divesites_ssi_table') }}
    WHERE id IS NOT NULL
      AND name IS NOT NULL
      AND SAFE_CAST(lat AS FLOAT64) IS NOT NULL
      AND SAFE_CAST(lng AS FLOAT64) IS NOT NULL
),

padi AS (
    SELECT
        CONCAT('padi:', CAST(id AS STRING))         AS site_id,
        title,
        CAST(latitude  AS FLOAT64)                  AS latitude,
        CAST(longitude AS FLOAT64)                  AS longitude,
        CAST(NULL AS STRING)                        AS country_iso3,
        CAST(NULL AS FLOAT64)                       AS avg_max_depth,
        CAST(NULL AS FLOAT64)                       AS avg_divetime,
        CAST(NULL AS FLOAT64)                       AS avg_visibility,
        CAST(NULL AS FLOAT64)                       AS avg_rating,
        CAST(NULL AS INT64)                         AS logged_dives,
        'padi'                                      AS site_source
    FROM {{ source('marine_data', 'divesites_padi_table') }}
    WHERE id        IS NOT NULL
      AND title     IS NOT NULL
      AND latitude  IS NOT NULL
      AND longitude IS NOT NULL
),

-- Lower-case, non-alphanumerics collapsed to single spaces: "Kudimaa (Wreck)" -> "kudimaa wreck"
ssi_norm AS (
    SELECT
        site_id,
        ST_GEOGPOINT(longitude, latitude)                                   AS geography,
        TRIM(REGEXP_REPLACE(LOWER(title), r'[^a-z0-9]+', ' '))              AS norm_title
    FROM ssi
),

padi_norm AS (
    SELECT
        site_id,
        ST_GEOGPOINT(longitude, latitude)                                   AS geography,
        TRIM(REGEXP_REPLACE(LOWER(title), r'[^a-z0-9]+', ' '))              AS norm_title
    FROM padi
),

padi_duplicates AS (
    SELECT DISTINCT p.site_id
    FROM padi_norm AS p
    INNER JOIN ssi_norm AS s
        ON ST_DWITHIN(p.geography, s.geography, 500)
    WHERE ST_DISTANCE(p.geography, s.geography) < 25
       -- Non-Latin names normalise to '' and must not match each other
       OR (
            p.norm_title != '' AND s.norm_title != ''
            AND (
                p.norm_title = s.norm_title
                OR (
                    LENGTH(p.norm_title) >= 4 AND LENGTH(s.norm_title) >= 4
                    AND (STRPOS(p.norm_title, s.norm_title) > 0 OR STRPOS(s.norm_title, p.norm_title) > 0)
                )
                OR 1 - EDIT_DISTANCE(p.norm_title, s.norm_title)
                       / GREATEST(LENGTH(p.norm_title), LENGTH(s.norm_title)) >= 0.8
            )
          )
),

combined AS (
    SELECT * FROM ssi

    UNION ALL

    SELECT * FROM padi
    WHERE site_id NOT IN (SELECT site_id FROM padi_duplicates)
)

SELECT
    site_id,
    title,
    latitude,
    longitude,
    country_iso3,
    avg_max_depth,
    avg_divetime,
    avg_visibility,
    avg_rating,
    logged_dives,
    site_source,
    ST_GEOGPOINT(longitude, latitude) AS geography
FROM combined

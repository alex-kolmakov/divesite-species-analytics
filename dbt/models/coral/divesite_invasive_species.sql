{{ config(materialized='table', cluster_by=['site_id']) }}

-- Invasiveness is a property of a species in a place: lionfish is invasive in the Caribbean and
-- native in the Red Sea. A species counts as invasive at a dive site when WRiMS lists it as
-- Invasive (or Of concern) in a Marine Regions area within 5 km of the site. The margin covers
-- shore sites whose coordinates sit on land and the ~1 km boundary simplification.
--
-- Resolution is WRiMS's: many records name a whole EEZ or sea (Australian EEZ, Eastern
-- Mediterranean), some a whole country or ocean ("United States", "North Atlantic"), so this is
-- "invasive in this site's region". It also lists brackish/freshwater invaders. Consumers should
-- intersect it with the species actually recorded at the site.

WITH site_regions AS (
    SELECT
        ds.site_id,
        r.mrgid
    FROM {{ ref('divesites') }} AS ds
    INNER JOIN {{ ref('wrims_regions') }} AS r
        ON ST_DWITHIN(r.geography, ds.geography, 5000)
),

alien AS (
    SELECT
        species,
        mrgid,
        invasiveness
    FROM {{ source('marine_data', 'wrims_table') }}
    WHERE invasiveness IN ('Invasive', 'Of concern')
)

SELECT
    sr.site_id,
    a.species,
    -- 'Invasive' wins over 'Of concern' when areas disagree
    IF(LOGICAL_OR(a.invasiveness = 'Invasive'), 'invasive', 'of concern') AS invasiveness,
    ARRAY_AGG(DISTINCT sr.mrgid ORDER BY sr.mrgid) AS mrgids
FROM site_regions AS sr
INNER JOIN alien AS a
    ON sr.mrgid = a.mrgid
GROUP BY sr.site_id, a.species

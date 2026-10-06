{{ config(materialized='table') }}

-- Marine Regions areas referenced by WRiMS, as geographies. A few boundaries need repair
-- (make_valid); an area that still can't be parsed is dropped rather than failing the build.

SELECT
    mrgid,
    SAFE.ST_GEOGFROMTEXT(wkt, make_valid => TRUE) AS geography
FROM {{ source('marine_data', 'wrims_regions_table') }}
WHERE SAFE.ST_GEOGFROMTEXT(wkt, make_valid => TRUE) IS NOT NULL

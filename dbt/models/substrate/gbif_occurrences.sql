{{ config(
    materialized='view',
) }}

SELECT 
    species, 
    GREATEST(IFNULL(individualcount, 1), 1) as individualcount,
    eventdate, 
    ST_GEOGPOINT(decimallongitude, decimallatitude) as geography,
FROM `bigquery-public-data.gbif.occurrences`

{% if env_var("DEVELOPMENT", "false") == "true" %} 
    TABLESAMPLE SYSTEM (0.01 PERCENT) 
{% endif %} 

WHERE eventdate IS NOT NULL 
and decimallongitude IS NOT NULL
and decimallatitude IS NOT NULL
and species IS NOT NULL


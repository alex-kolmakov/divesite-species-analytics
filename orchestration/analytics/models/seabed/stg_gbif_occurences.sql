{{ config(materialized='table') }}

SELECT 
    species, 
    individualcount, 
    eventdate, 
    ST_GEOGPOINT(decimallongitude, decimallatitude) as geography,
    'GBIF' as source
FROM `bigquery-public-data.gbif.occurrences`

{% if var("development", default=False) %} 
    TABLESAMPLE SYSTEM (1 PERCENT) 
{% endif %} 

WHERE decimallatitude BETWEEN {{env_var('LATTITUDE_BOTTOM')}} AND {{env_var('LATTITUDE_TOP')}}
    AND decimallongitude BETWEEN {{env_var('LONGITUDE_LEFT')}} AND {{env_var('LONGITUDE_RIGHT')}}
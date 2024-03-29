{{ config(
    enabled=true, 
    materialized='table',     
    partition_by={
      "field": "eventdate",
      "data_type": "timestamp",
      "granularity": "month"
    }, 
    cluster_by=['geography']) 
}}

SELECT 
    species, 
    SAFE_CAST(individualCount AS INT64) as individualcount, 
    SAFE_CAST(eventDate AS TIMESTAMP) as eventdate, 
    ST_GEOGPOINT(decimalLongitude, decimalLatitude) as geography
FROM {{ source('marine_data', 'obis_table') }}
WHERE eventDate IS NOT NULL 
    AND species IS NOT NULL
    AND individualCount IS NOT NULL
    AND decimalLatitude BETWEEN {{vars('LATTITUDE_BOTTOM')}} AND {{vars('LATTITUDE_TOP')}}
    AND decimalLongitude BETWEEN {{vars('LONGITUDE_LEFT')}} AND {{vars('LONGITUDE_RIGHT')}}

UNION ALL

SELECT 
    species, 
    individualcount, 
    eventdate, 
    ST_GEOGPOINT(decimallongitude, decimallatitude) as geography
FROM `bigquery-public-data.gbif.occurrences` 
WHERE countrycode = 'AE'
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

with combined_table as (

    SELECT 
        species, 
        SAFE_CAST(individualCount AS INT64) as individualcount, 
        SAFE_CAST(eventDate AS TIMESTAMP) as eventdate, 
        ST_GEOGPOINT(decimalLongitude, decimalLatitude) as geography
    FROM {{ source('marine_data', 'obis_table') }}
    WHERE decimalLatitude BETWEEN {{var('LATTITUDE_BOTTOM')}} AND {{var('LATTITUDE_TOP')}}
        AND decimalLongitude BETWEEN {{var('LONGITUDE_LEFT')}} AND {{var('LONGITUDE_RIGHT')}}

    UNION ALL

    SELECT 
        species, 
        individualcount, 
        eventdate, 
        ST_GEOGPOINT(decimallongitude, decimallatitude) as geography
    FROM `bigquery-public-data.gbif.occurrences` 
    WHERE decimallatitude BETWEEN {{var('LATTITUDE_BOTTOM')}} AND {{var('LATTITUDE_TOP')}}
        AND decimallongitude BETWEEN {{var('LONGITUDE_LEFT')}} AND {{var('LONGITUDE_RIGHT')}}

    UNION ALL

    SELECT 
        species, 
        SAFE_CAST(individualCount AS INT64) as individualcount, 
        SAFE_CAST(date AS TIMESTAMP) as eventdate, 
        ST_GEOGPOINT(longitude, latitude) as geography
    FROM {{ source('marine_data', 'reef_check_table') }}
    WHERE latitude BETWEEN {{var('LATTITUDE_BOTTOM')}} AND {{var('LATTITUDE_TOP')}}
    AND longitude BETWEEN {{var('LONGITUDE_LEFT')}} AND {{var('LONGITUDE_RIGHT')}}

)

SELECT * FROM combined_table
WHERE species IS NOT NULL 
    AND individualcount IS NOT NULL 
    AND eventdate IS NOT NULL 
    AND geography IS NOT NULL
{{ config(enabled=true, materialized='table', cluster_by=['geography']) }}

SELECT 
    title, 
    ST_GEOGPOINT(longitude, latitude) as geography
FROM {{ source('marine_data', 'divesites_table') }}
WHERE title IS NOT NULL 
AND latitude BETWEEN {{vars('LATTITUDE_BOTTOM')}} AND {{vars('LATTITUDE_TOP')}}
AND longitude BETWEEN {{vars('LONGITUDE_LEFT')}} AND {{vars('LONGITUDE_RIGHT')}}
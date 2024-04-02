{{ config(enabled=true, materialized='table', cluster_by=['geography']) }}

SELECT 
    title, 
    ST_GEOGPOINT(longitude, latitude) as geography
FROM {{ source('marine_data', 'divesites_table') }}
WHERE title IS NOT NULL 
AND latitude BETWEEN {{var('LATTITUDE_BOTTOM')}} AND {{var('LATTITUDE_TOP')}}
AND longitude BETWEEN {{var('LONGITUDE_LEFT')}} AND {{var('LONGITUDE_RIGHT')}}
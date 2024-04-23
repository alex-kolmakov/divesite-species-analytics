{{ config(enabled=true, materialized='table', cluster_by=['geography']) }}

SELECT 
    title, 
    ST_GEOGPOINT(longitude, latitude) as geography
FROM {{ source('marine_data', 'divesites_table') }}
WHERE title IS NOT NULL 
AND latitude BETWEEN {{env_var('LATTITUDE_BOTTOM')}} AND {{env_var('LATTITUDE_TOP')}}
AND longitude BETWEEN {{env_var('LONGITUDE_LEFT')}} AND {{env_var('LONGITUDE_RIGHT')}}
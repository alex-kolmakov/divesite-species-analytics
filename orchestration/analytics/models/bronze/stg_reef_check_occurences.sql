SELECT 
    species, 
    SAFE_CAST(individualCount AS INT64) as individualcount, 
    SAFE_CAST(date AS TIMESTAMP) as eventdate, 
    ST_GEOGPOINT(longitude, latitude) as geography,
    'REEF_CHECK' as source
FROM {{ source('marine_data', 'reef_check_table') }}
WHERE latitude BETWEEN {{env_var('LATTITUDE_BOTTOM')}} AND {{env_var('LATTITUDE_TOP')}}
AND longitude BETWEEN {{env_var('LONGITUDE_LEFT')}} AND {{env_var('LONGITUDE_RIGHT')}}

{% if var("development", default=true) %} 
    LIMIT 100 
{% endif %}
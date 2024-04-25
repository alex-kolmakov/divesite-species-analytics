{{ config(enabled=true, materialized='table') }}


SELECT 
    species, 
    SAFE_CAST(individualCount AS INT) as individualcount, 
    SAFE_CAST(eventDate AS TIMESTAMP) as eventdate, 
    ST_GEOGPOINT(decimalLongitude, decimalLatitude) as geography,
    'OBIS' as source
FROM {{ source('marine_data', 'obis_table') }}

{% if var("development", default=true) %} 
    LIMIT 100 
{% endif %} 

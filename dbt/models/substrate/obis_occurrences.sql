{{ config(
    materialized='view',
) }}

SELECT 
    species, 
    GREATEST(IFNULL(SAFE_CAST(individualCount AS INT), 1), 1) as individualcount,
    SAFE_CAST(eventDate AS TIMESTAMP) as eventdate, 
    ST_GEOGPOINT(decimalLongitude, decimalLatitude) as geography,
FROM {{ source('marine_data', 'obis_table') }}
WHERE 
    SAFE_CAST(eventDate AS TIMESTAMP) IS NOT NULL AND 
    decimalLongitude IS NOT NULL AND 
    decimalLatitude IS NOT NULL AND 
    species IS NOT NULL

{% if env_var("DEVELOPMENT", "false") == "true" %}
    AND MOD(FARM_FINGERPRINT(species), 100) = 0
{% endif %}

-- marine_species.sql

{{ config(materialized='table') }}

SELECT species 
FROM marine_data.local_data 
WHERE eventdate >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 160 DAY)
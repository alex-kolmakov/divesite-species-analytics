{{ config(enabled=true, materialized='table') }}

SELECT
    o.*
FROM {{ref("stg_occurences")}} o
JOIN {{ source('marine_data', 'invasive_species_table') }} i
  ON o.species = i.scientificName
WHERE o.individualcount > 0 and o.species IS NOT NULL
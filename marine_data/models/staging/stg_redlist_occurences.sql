{{ config(enabled=true, materialized='table') }}

SELECT
    o.*
FROM {{ref("stg_occurences")}} o
JOIN {{ source('marine_data', 'redlist_species_table') }} i
  ON o.species = i.scientificName
WHERE o.individualcount > 0 and o.species IS NOT NULL and o.eventdate IS NOT NULL
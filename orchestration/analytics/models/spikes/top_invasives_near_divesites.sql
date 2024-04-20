{{ config(materialized='table') }}

SELECT
    p.species, 
    i.imageUrl,
    SUM(p.individualcount) AS total_invasive_individuals
FROM {{ref('divesite_invasive_proximity')}} p
JOIN {{ source('marine_data', 'invasive_species_table') }} i
  ON p.species = i.scientificName
WHERE i.imageUrl IS NOT NULL
GROUP BY p.species, i.imageUrl
ORDER BY total_invasive_individuals DESC
LIMIT 20
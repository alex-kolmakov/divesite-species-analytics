-- Aggregated sighting counts must be at least 1 (COUNT(*) guarantees this,
-- but guards against future changes that might introduce zeros).

SELECT *
FROM {{ ref('divesite_species_frequency') }}
WHERE sighting_count <= 0

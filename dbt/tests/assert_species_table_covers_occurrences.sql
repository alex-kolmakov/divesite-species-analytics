-- Every species present in occurrences should have a row in the species table.
-- A missing species means the deduplication logic in species.sql dropped it.

SELECT DISTINCT occ.species
FROM {{ ref('occurrences') }} AS occ
LEFT JOIN {{ ref('species') }} AS sp
    ON occ.species = sp.species
WHERE sp.species IS NULL

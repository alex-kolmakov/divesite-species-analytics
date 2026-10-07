-- For each dive site, the minimum frequency rank should be 1.
-- If no rank-1 entry exists for a site, the ranking logic is broken.

SELECT site_id
FROM {{ ref('divesite_species_frequency') }}
GROUP BY site_id
HAVING MIN(frequency_rank) != 1

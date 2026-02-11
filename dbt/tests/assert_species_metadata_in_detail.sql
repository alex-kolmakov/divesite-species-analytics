-- The denormalized detail table should carry species_type for every row.
-- The UI uses this to render endangered/invasive badges. A NULL species_type
-- means the JOIN to the species table failed.

SELECT *
FROM {{ ref('divesite_species_detail') }}
WHERE species_type IS NULL
   OR species_type NOT IN ('endangered', 'invasive', 'normal')

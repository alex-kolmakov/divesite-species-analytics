-- species_type should be consistent with the boolean flags:
--   is_endangered = TRUE  → species_type = 'endangered'
--   is_invasive = TRUE (and not endangered) → species_type = 'invasive'
--   both FALSE → species_type = 'normal'

SELECT *
FROM {{ ref('species') }}
WHERE
    (is_endangered = TRUE AND species_type != 'endangered')
    OR (is_endangered = FALSE AND is_invasive = TRUE AND species_type != 'invasive')
    OR (is_endangered = FALSE AND is_invasive = FALSE AND species_type != 'normal')

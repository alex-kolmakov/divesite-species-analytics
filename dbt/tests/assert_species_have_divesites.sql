-- Use Case 1 validation: species in the species table should appear in species_summary
-- (i.e. have at least one dive site association). We allow most species to have no nearby
-- dive site, but a collapse below 1% means the spatial join or the summary broke.

SELECT 'too_few_species_at_divesites' AS failure_reason
FROM (
    SELECT
        (SELECT COUNT(*) FROM {{ ref('species_summary') }}) AS species_with_sites,
        (SELECT COUNT(*) FROM {{ ref('species') }}) AS total_species
)
WHERE species_with_sites < total_species * 0.01

-- Use Case 1 validation: species in the species table should appear in
-- species_divesite_summary (i.e. have at least one dive site association).
-- Species with zero dive site matches would show an empty map in the UI.
-- We allow some species to have no nearby dive sites, but the majority should.

SELECT 'too_few_species_at_divesites' AS failure_reason
FROM (
    SELECT
        (SELECT COUNT(DISTINCT species) FROM {{ ref('species_divesite_summary') }}) AS species_with_sites,
        (SELECT COUNT(*) FROM {{ ref('species') }}) AS total_species
)
WHERE species_with_sites < total_species * 0.01

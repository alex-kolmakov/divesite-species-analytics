-- Use Case 2 validation: most dive sites in divesite_summary should have
-- at least one species. A dive site with total_species = 0 would show an
-- empty species panel in the UI. Some remote sites may legitimately have
-- no nearby occurrences, but at least half should have data.

SELECT 'too_many_empty_divesites' AS failure_reason
FROM (
    SELECT
        COUNTIF(total_species > 0) AS sites_with_species,
        COUNT(*) AS total_sites
    FROM {{ ref('divesite_summary') }}
)
WHERE sites_with_species < total_sites * 0.5

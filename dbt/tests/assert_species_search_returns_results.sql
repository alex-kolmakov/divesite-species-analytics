-- Simulates the species search typeahead: at least some species should be findable
-- by common name. If this fails, enrichment hasn't populated common_name or the
-- species_enrichment table is empty. Configured as warn-only since enrichment
-- runs separately from dbt.

{{ config(severity='warn') }}

SELECT 'no_searchable_species' AS failure_reason
FROM (
    SELECT COUNT(*) AS cnt
    FROM {{ source('marine_data', 'species_enrichment') }}
    WHERE common_name IS NOT NULL
)
WHERE cnt = 0

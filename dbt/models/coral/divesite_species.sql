{{ config(materialized='table', cluster_by=['site_id']) }}

-- App table: species at each dive site, with per-site counts, best-place metrics and the per-site
-- invasive label. Narrow on purpose: names, descriptions and images live once per species in
-- species_summary, so the app doesn't hold the same description on thousands of site rows.

SELECT
    freq.site_id,
    freq.species,
    freq.sighting_count,
    freq.days_seen,
    freq.days_seen_recent,
    freq.first_seen,
    freq.last_seen,
    freq.months_seen,
    freq.best_place_score,
    freq.frequency_rank,
    freq.best_place_rank,
    inv.invasiveness,
    COALESCE(inv.invasiveness = 'invasive', FALSE) AS is_invasive_here
FROM {{ ref('divesite_species_frequency') }} AS freq
LEFT JOIN {{ ref('divesite_invasive_species') }} AS inv
    ON freq.site_id = inv.site_id AND freq.species = inv.species

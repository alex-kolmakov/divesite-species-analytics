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
    -- Most recorded at the site among the species the site list shows (birds excluded, NULL for them)
    IF(
        sp.taxon_class = 'Aves',
        NULL,
        RANK() OVER (PARTITION BY freq.site_id, sp.taxon_class = 'Aves' ORDER BY freq.sighting_count DESC)
    ) AS frequency_rank,
    freq.best_place_rank,
    inv.invasiveness,
    COALESCE(inv.invasiveness = 'invasive', FALSE) AS is_invasive_here,
    -- Seabirds are in WoRMS and in the records, but not what a diver sees: hidden from site lists
    -- and site counts, still on the bird's own species page
    COALESCE(sp.taxon_class = 'Aves', FALSE) AS is_bird
FROM {{ ref('divesite_species_frequency') }} AS freq
INNER JOIN {{ ref('species') }} AS sp
    ON freq.species = sp.species
LEFT JOIN {{ ref('divesite_invasive_species') }} AS inv
    ON freq.site_id = inv.site_id AND freq.species = inv.species

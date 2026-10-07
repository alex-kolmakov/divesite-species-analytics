-- Reconciliation: for a fixed sample of dive sites, the pairs in near_dive_site_occurrences must
-- equal a plain recount against occurrences. This measures what the join lost or multiplied, not
-- the shape of what survived: it fails when pairs are dropped (the old PARTITION BY event_date
-- ranking kept one pair per timestamp worldwide) and when they fan out.
--
-- Sample: 50 SSI sites, the most-logged and one hash-picked site from each of the 25 countries
-- with the most sites (SSI IDs are stable; PADI IDs churn between scrapes). It includes inland
-- pools and quarries, which must reconcile at zero.
--
-- Cost: a full recount scans occurrence_key + geography (~29 GiB). The join can't use the
-- clustering on geography, but event_date partitions prune exactly, so the recount is limited to
-- the months below (~1 GiB). Widen the list to test more; a bug confined to other months is not
-- seen here.

{% set sample_site_ids = [
    'ssi:105764', 'ssi:8123', 'ssi:273481', 'ssi:63731', 'ssi:110401',
    'ssi:3007', 'ssi:83913', 'ssi:204067', 'ssi:27579', 'ssi:23907',
    'ssi:60829', 'ssi:310711', 'ssi:198548', 'ssi:357002', 'ssi:91189',
    'ssi:282134', 'ssi:47524', 'ssi:94233', 'ssi:116977', 'ssi:565751',
    'ssi:132610', 'ssi:580827', 'ssi:78608', 'ssi:130507', 'ssi:221619',
    'ssi:873959', 'ssi:290490', 'ssi:223794', 'ssi:110705', 'ssi:14343',
    'ssi:90753', 'ssi:387842', 'ssi:68417', 'ssi:494479', 'ssi:122925',
    'ssi:48653', 'ssi:120461', 'ssi:290241', 'ssi:11515', 'ssi:269584',
    'ssi:241798', 'ssi:668277', 'ssi:151747', 'ssi:254572', 'ssi:64407',
    'ssi:681941', 'ssi:75233', 'ssi:254847', 'ssi:74316', 'ssi:191783'
] %}

{% set sample_months = [
    '1975-02-01', '1988-11-01', '1995-06-01', '2003-04-01', '2009-12-01', '2012-03-01',
    '2016-08-01', '2019-09-01', '2021-01-01', '2022-05-01', '2024-07-01', '2025-10-01'
] %}

WITH sample_sites AS (
    SELECT site_id, geography
    FROM {{ ref('divesites') }}
    WHERE site_id IN ('{{ sample_site_ids | join("', '") }}')
),

sample_occurrences AS (
    SELECT occurrence_key, geography
    FROM {{ ref('occurrences') }}
    WHERE (
        {% for month in sample_months -%}
        (event_date >= TIMESTAMP('{{ month }}') AND event_date < TIMESTAMP(DATE_ADD(DATE '{{ month }}', INTERVAL 1 MONTH)))
        {%- if not loop.last %} OR{% endif %}
        {% endfor -%}
    )
    {% if env_var("DEVELOPMENT", "false") == "true" -%}
    -- same species subsample as the model
    AND MOD(FARM_FINGERPRINT(species), 20) = 0
    {%- endif %}
),

recount AS (
    SELECT
        s.site_id,
        COUNT(DISTINCT occ.occurrence_key) AS pairs
    FROM sample_occurrences AS occ
    CROSS JOIN sample_sites AS s
    WHERE ST_DWITHIN(occ.geography, s.geography, {{ env_var('PROXIMITY_METERS') }})
    GROUP BY s.site_id
),

model AS (
    SELECT
        site_id,
        COUNT(*) AS pairs
    FROM {{ ref('near_dive_site_occurrences') }}
    WHERE site_id IN ('{{ sample_site_ids | join("', '") }}')
      AND DATE_TRUNC(DATE(event_date), MONTH) IN ('{{ sample_months | join("', '") }}')
    GROUP BY site_id
)

SELECT
    s.site_id,
    'pair count differs from recount' AS failure_reason,
    COALESCE(recount.pairs, 0) AS recount_pairs,
    COALESCE(model.pairs, 0)   AS model_pairs
FROM sample_sites AS s
LEFT JOIN recount ON s.site_id = recount.site_id
LEFT JOIN model ON s.site_id = model.site_id
WHERE COALESCE(recount.pairs, 0) != COALESCE(model.pairs, 0)

UNION ALL

-- A sample site that left divesites would silently shrink the test
SELECT
    site_id,
    'sample site missing from divesites' AS failure_reason,
    NULL AS recount_pairs,
    NULL AS model_pairs
FROM UNNEST(['{{ sample_site_ids | join("', '") }}']) AS site_id
WHERE site_id NOT IN (SELECT site_id FROM sample_sites)

UNION ALL

-- An empty recount would make the comparison pass without comparing anything
SELECT
    CAST(NULL AS STRING) AS site_id,
    'recount found no pairs for the sample' AS failure_reason,
    0 AS recount_pairs,
    NULL AS model_pairs
FROM (SELECT COUNT(*) AS sites_with_pairs FROM recount)
WHERE sites_with_pairs = 0

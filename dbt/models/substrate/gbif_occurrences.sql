{{ config(
    materialized='table',
    cluster_by=['species'],
) }}

-- One scan of the GBIF public table. It has 3.7B rows and no partitioning or clustering, so every
-- column read is billed in full on every query (~306 GiB for this column set, 2026-10). This table
-- is the only place that pays it: everything downstream, tests included, reads the copy here.
-- Rebuild it only when refreshing GBIF (dbt build --select gbif_occurrences+).
--
-- Only WoRMS species are kept (a semi-join, so homonyms in WoRMS can't duplicate rows). Nothing
-- else is filtered: absences, basis of record, coordinate uncertainty and dates are judged in
-- `occurrences`, so every rule can be changed and counted without scanning GBIF again.
-- occurrenceid/datasetkey (262 GiB more) are left out; cross-source dedup uses species, day and
-- location instead.

SELECT
    gbifid                              AS gbif_id,
    species,
    individualcount,
    eventdate,
    decimallongitude,
    decimallatitude,
    coordinateuncertaintyinmeters       AS coordinate_uncertainty_m,
    occurrencestatus                    AS occurrence_status,
    basisofrecord                       AS basis_of_record,
FROM `bigquery-public-data.gbif.occurrences`

{% if env_var("DEVELOPMENT", "false") == "true" %}
    TABLESAMPLE SYSTEM (0.01 PERCENT)
{% endif %}

WHERE species IN (
    SELECT scientificName FROM {{ source('marine_data', 'worms_table') }}
)

{{ config(
    materialized='table',
    cluster_by=['species'],
) }}

-- One read of the OBIS parquet in GCS (~6 GB file, ~50 GiB billed: external parquet is billed at
-- its uncompressed size). Downstream models and tests read this native copy instead.
-- Rebuild it only after re-ingesting OBIS (dbt build --select obis_occurrences+).
--
-- Only WoRMS species are kept. Absence records, rows OBIS QC dropped and rows without a valid
-- date are kept here and filtered in `occurrences`, so each rule can be counted.
-- The date to use is date_mid (OBIS-validated, epoch ms), never the free-text eventDate.

SELECT
    obis_id,
    dataset_id,
    species,
    individualCount                     AS individualcount,
    date_mid,
    decimalLongitude                    AS decimallongitude,
    decimalLatitude                     AS decimallatitude,
    coordinateUncertaintyInMeters       AS coordinate_uncertainty_m,
    basisOfRecord                       AS basis_of_record,
    absence,
    dropped,
    flags,
FROM {{ source('marine_data', 'obis_table') }}
WHERE species IN (
    SELECT scientificName FROM {{ source('marine_data', 'worms_table') }}
)

{% if env_var("DEVELOPMENT", "false") == "true" %}
    AND MOD(FARM_FINGERPRINT(species), 100) = 0
{% endif %}

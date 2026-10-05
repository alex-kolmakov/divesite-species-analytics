{{ config(
    materialized='view',
) }}

-- The date comes from OBIS's validated date_mid (epoch ms), never from the free-text eventDate:
-- OBIS leaves date_mid/date_year null when it can't parse a date, while eventDate still holds
-- strings like '0000-00-00' or '3798-06-28' that SAFE_CAST turned into years 1 to 9840.
-- Absence records ("looked, not found") and rows OBIS QC dropped (on land, not marine) are excluded.

SELECT
    obis_id,
    dataset_id,
    occurrenceID AS occurrence_id,
    species,
    GREATEST(IFNULL(SAFE_CAST(individualCount AS INT), 1), 1) as individualcount,
    TIMESTAMP_MILLIS(date_mid) as eventdate,
    ST_GEOGPOINT(decimalLongitude, decimalLatitude) as geography,
    coordinateUncertaintyInMeters AS coordinate_uncertainty_m,
    basisOfRecord AS basis_of_record,
    flags,
FROM {{ source('marine_data', 'obis_table') }}
WHERE
    date_mid IS NOT NULL AND
    decimalLongitude IS NOT NULL AND
    decimalLatitude IS NOT NULL AND
    species IS NOT NULL AND
    absence IS NOT TRUE AND
    dropped IS NOT TRUE

{% if env_var("DEVELOPMENT", "false") == "true" %}
    AND MOD(FARM_FINGERPRINT(species), 100) = 0
{% endif %}

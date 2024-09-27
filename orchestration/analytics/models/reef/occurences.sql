{{ config(
    materialized='table',
    partition_by={
        "field": "event_date",
        "data_type": "timestamp",
        "granularity": "month"
    }, 
    cluster_by=['geography']
)}}

-- Standardize GBIF data
WITH gbif_standardized AS (
    SELECT 
        eventDate AS event_date,
        species,
        individualCount AS individual_count,
        geography,
        'GBIF' AS source
    FROM {{ ref('gbif_occurrences') }}
),

-- Standardize OBIS data
obis_standardized AS (
    SELECT 
        eventDate AS event_date,
        species,
        individualCount AS individual_count,
        geography,
        'OBIS' AS source
    FROM {{ ref('obis_occurrences') }}
),

total_occurences AS (
    SELECT * FROM gbif_standardized
    UNION ALL
    SELECT * FROM obis_standardized
)

SELECT 
    occ.*
FROM total_occurences AS occ
INNER JOIN {{ source('marine_data', 'worms_table') }} AS worms
    ON occ.species = worms.scientificName
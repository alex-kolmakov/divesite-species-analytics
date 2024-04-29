{{ config(
    enabled=true, 
    materialized='table',     
    partition_by={
      "field": "eventdate",
      "data_type": "timestamp",
      "granularity": "month"
    }, 
    cluster_by=['geography']) 
}}

SELECT occurences.*,
    CASE 
        WHEN invasive.scientificName IS NOT NULL THEN TRUE
        ELSE NULL
    END AS is_invasive,
    CASE 
        WHEN redlist.scientificName IS NOT NULL THEN TRUE
        ELSE NULL
    END AS is_endangered
FROM (
    SELECT * FROM {{ ref('stg_gbif_occurences') }}
    UNION ALL
    SELECT * FROM {{ ref('stg_obis_occurences') }}
    UNION ALL
    SELECT * FROM {{ ref('stg_reef_check_occurences') }}

) AS occurences

LEFT JOIN {{ source('marine_data', 'invasive_species_table') }} AS invasive
    ON occurences.species = invasive.scientificName
LEFT JOIN {{ source('marine_data', 'redlist_species_table') }} AS redlist
    ON occurences.species = redlist.scientificName

WHERE occurences.species IS NOT NULL 
    AND occurences.individualcount > 0
    AND occurences.eventdate IS NOT NULL 
    AND occurences.geography IS NOT NULL
-- marine_species.sql

{{ config(materialized='table') }}

SELECT * 
FROM {{ source("marine_data", "invasive_species_table") }}
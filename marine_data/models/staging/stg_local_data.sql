-- marine_species.sql

{{ config(materialized='table') }}

SELECT species 
FROM marine_data.invasive_data
{{ config(materialized='table') }}

SELECT
    title,
    EXTRACT(month FROM eventdate) AS observation_month, 
    species, 
    SUM(individualcount) AS total_redlist_individuals
FROM {{ref('divesite_redlist_proximity')}}
GROUP BY 1, 2, 3
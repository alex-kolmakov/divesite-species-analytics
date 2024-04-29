{{ config(materialized='view') }}

SELECT COUNT(*) as total_observations_from_source, source
FROM {{ ref('divesite_proximity') }}
GROUP BY source
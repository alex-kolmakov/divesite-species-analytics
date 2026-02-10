{{ config(
    materialized='table',
    cluster_by=['species']
)}}


SELECT * FROM {{ ref('occurrences') }}
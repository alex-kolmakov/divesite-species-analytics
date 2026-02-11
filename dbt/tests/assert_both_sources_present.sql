-- The occurrences table should contain data from both GBIF and OBIS.
-- If either source is missing, the ingestion or union logic may have failed.

SELECT 'missing_source' AS failure_reason
FROM (
    SELECT COUNT(DISTINCT source) AS source_count
    FROM {{ ref('occurrences') }}
)
WHERE source_count < 2

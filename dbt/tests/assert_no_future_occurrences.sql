-- Occurrence dates should not be in the future.
-- Future dates indicate bad source data or parsing errors.

SELECT *
FROM {{ ref('occurrences') }}
WHERE event_date > CURRENT_TIMESTAMP()

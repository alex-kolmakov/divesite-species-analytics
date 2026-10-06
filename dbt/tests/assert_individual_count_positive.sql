-- Recorded counts must be positive: a count of 0 is an absence and is filtered out in
-- occurrences. Null means "not recorded" and is allowed.

SELECT *
FROM {{ ref('occurrences') }}
WHERE individual_count <= 0

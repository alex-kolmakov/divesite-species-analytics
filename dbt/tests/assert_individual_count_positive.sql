-- Occurrences should never have zero or negative individual counts.
-- The IFNULL(..., 1) default in substrate should guarantee this.

SELECT *
FROM {{ ref('occurrences') }}
WHERE individual_count <= 0

-- Map rendering requires valid coordinates. Latitude must be [-90, 90],
-- longitude must be [-180, 180]. Invalid coordinates would place markers
-- off the map or crash the map component.

SELECT *
FROM {{ ref('divesite_summary') }}
WHERE latitude < -90 OR latitude > 90
   OR longitude < -180 OR longitude > 180
   OR latitude IS NULL
   OR longitude IS NULL

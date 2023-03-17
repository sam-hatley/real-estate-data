{{ config(materialized='table') }}

WITH tmp AS(
  SELECT
    DISTINCT(Agent),
    SUM(Price) AS Port_Value,
    COUNT(*) AS Listings
  FROM {{ ref('added_london_daily') }}
  GROUP BY Agent
)
SELECT
  Agent,
  Port_Value,
  Listings,
  CAST(ROUND(Port_Value / Listings, 0) AS INT) AS Avg_Val
FROM tmp
WHERE Agent IS NOT NULL
ORDER BY tmp.Port_Value DESC
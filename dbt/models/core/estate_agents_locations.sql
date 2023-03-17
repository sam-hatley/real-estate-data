{{ config(materialized='table') }}

SELECT
  Agent,
  Outcode,
  Count(*) AS Prop_Count,
  CAST(ROUND(AVG(Price), 0) AS INT) AS Avg_Price
FROM {{ ref('added_london_daily') }}
WHERE Outcode IS NOT NULL
  AND Agent IS NOT NULL
GROUP BY Agent, Outcode
ORDER BY Agent, Avg_Price DESC
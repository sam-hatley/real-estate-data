{{ config(
    materialized='table',
    partition_by={
      "field": "Date",
      "data_type": "DATE",
      "granularity": "day"
    }
)}}

-- Order duplicate ids in order of recency
WITH recent_rank AS(
  SELECT 
    id,
    Address,
    Outcode,
    Postcode,
    Price,
    Price_Qualifier,
    Listing_Type,
    CAST(Date AS DATE) AS Date,
    Property_Type,
    Bedrooms,
    Bathrooms,
    Size,
    Tenure,
    Agent,
    Agent_Long,
    Agent_Address,
    ROW_NUMBER() OVER (PARTITION BY id ORDER BY Date DESC) AS rnk
  FROM {{ ref('stg_all_london_daily') }}
)

-- Select only the most recent records
SELECT
    id,
    Address,
    Outcode,
    Postcode,
    Price,
    Price_Qualifier,
    Listing_Type,
    Date,
    Property_Type,
    Bedrooms,
    Bathrooms,
    Size,
    Tenure,
    Agent,
    Agent_Long,
    Agent_Address
FROM recent_rank
WHERE rnk = 1
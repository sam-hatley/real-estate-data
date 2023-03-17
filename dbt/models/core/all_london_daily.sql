{{ config(
    materialized='table',
    partition_by={
      "field": "Date",
      "data_type": "DATE",
      "granularity": "day"
    }
)}}

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
    Agent_Address
FROM {{ ref('stg_all_london_daily') }}
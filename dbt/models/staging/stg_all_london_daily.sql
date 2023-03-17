--dbt run --select stg_green_tripdata

{{ config(materialized='view') }}

SELECT id,
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
FROM {{ source('staging','all_london_daily_external') }}
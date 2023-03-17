from urllib.parse import urlencode
from bs4 import BeautifulSoup as bs
import requests
from datetime import datetime, timedelta
import re
import pandas as pd
import numpy as np
import random
import time
from prefect import flow, task
from prefect_gcp.cloud_storage import GcsBucket
import os
from yaml import safe_load


def get_rightmove_url(
    locationIdentifier="REGION^87490",  # This is set to "London"
    sortType=6,
    index=0,
    propertyTypes="bungalow,detached,flat,park-home,semi-detached,terraced",
    maxDaysSinceAdded=1,
    mustHave="",
    dontShow="",
    furnishTypes="",
    keywords="",
) -> str:
    """Generates a rightmove query URL from optional parameters. Defaults
    to the first page of listings posted within the last day in London."""

    params = {
        "locationIdentifier": locationIdentifier,
        "sortType": sortType,
        "index": index,
        "propertyTypes": propertyTypes,
        "maxDaysSinceAdded": maxDaysSinceAdded,
        "mustHave": mustHave,
        "dontShow": dontShow,
        "furnishTypes": furnishTypes,
        "keywords": keywords,
    }

    # Generate the URL from the parameters given
    url = "https://www.rightmove.co.uk/property-for-sale/find.html?" + urlencode(params)
    return url


@task(log_prints=True, retries=3)
def get_rightmove_results(url: str, is_testrun: bool) -> list:
    """Gets the URLs for individual properties listed on rightmove within one
    day. Takes a query URL with index of 0 or none and returns a list of
    property listing URLs."""

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:108.0) Gecko/20100101 Firefox/108.0"
    }
    page = requests.get(url, headers=headers)
    soup = bs(page.content, "html.parser")

    # Get the number of results from this query and find number of
    # pages to return. Rightmove displays 24 results to a page.
    result_count = int(soup.find("span", class_="searchHeader-resultCount").get_text())
    page_count = int(round(result_count / 24, 0)) - 1
    # Ensure we're capturing the last pages of results.
    page_count += 1 if result_count % 24 > 0 else 0

    # Iterate through each page and fetch the URL
    property_links = []
    i = 0
    print(f"Scraping {page_count} pages for results.")
    for page in range(0, page_count):
        if i > 0:
            url = get_rightmove_url(index=i * 24)
            page = requests.get(url)
            soup = bs(page.content, "html.parser")
            time.sleep(random.uniform(2, 8))

        # Grabbing all property cards and slicing off the first listing, which is
        # always a "featured property" and may not be relevant to our search
        property_cards = soup.find_all("div", class_="l-searchResult is-list")
        property_cards = property_cards[1:]

        for card in property_cards:
            property_link = card.find(
                "a", class_="propertyCard-priceLink propertyCard-salePrice"
            ).attrs["href"]
            property_links.append(property_link)
        if is_testrun:
            break
        i += 1

    return property_links


@task(log_prints=True, retries=3)
def scrape_page(link: str) -> dict:
    """Scrapes a single rightmove page for data. Returns data in the form of a dictionary."""

    url = "https://www.rightmove.co.uk" + link

    id = re.findall("([0-9]{7,15})", link)[0]
    id = int(id)
    print(f"Scraping {id}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:108.0) Gecko/20100101 Firefox/108.0"
    }

    try:
        page = requests.get(url, headers=headers, timeout=5)
    except requests.ConnectionError:
        t = random.uniform(60, 120)
        print(f"CONNECTION ERROR. Waiting {t} seconds.")
        time.sleep(t)
        page = requests.get(url, headers=headers, timeout=5)

    soup = bs(page.content, "html.parser")

    # Fetch address and search for Postcode, Outcode
    Address = np.nan
    Outcode = np.nan
    Postcode = np.nan

    Address = soup.find("h1", itemprop="streetAddress").text
    Address = Address.replace("\r", "")
    Address = Address.replace("\n", " ")

    code = Address.split(",")[-1]

    try:
        Postcode = re.findall(
            "[A-Z]{1,2}[0-9][A-Z0-9]? [0-9][ABD-HJLNP-UW-Z]{2}", code
        )[0]
    except:
        Postcode = np.nan

    if pd.isnull(Postcode):
        try:
            Outcode = re.findall("[A-Z]{1,2}[0-9][A-Z0-9]?", code)[0]
        except:
            Outcode = np.nan
    else:
        Outcode = Postcode.split(" ")[0]

    # Rightmove relies on dynamically-generated CSS class names, so we'll
    # instead use cues from the page's structure to find the information we
    # need. Articles are spaced evenly, and their general format should not
    # change.
    articles = soup.find_all("article")

    # Setting vars to NaN values in case they don't exist in the listing
    Price = np.nan
    Listing_Type = np.nan
    Date = np.nan

    # The first article has property images, the second has price/date information
    # Pulling price and date, avoiding the latter loop with would overwrite price if
    # "£" appears in the property description.

    # A slightly different method to add the price qualifier
    try:
        Price_Qualifier = (
            articles[1].find("div", attrs={"data-testid": "priceQualifier"}).text
        )
    except AttributeError:
        Price_Qualifier = np.nan

    for string in articles[1].stripped_strings:
        if "£" in string:
            Price = string.replace("£", "")  # Full number in format "(xxx,)xxx,xxx"
            Price = int(Price.replace(",", ""))
        elif "Added" in string or "Reduced" in string:
            listing = (
                string  # This includes "added on" or "price increased/decreased", etc.
            )
            listing = listing.split(" ")
            Listing_Type = listing[0]
            if listing[-1] == "today":
                Date = datetime.now().strftime("%Y-%m-%d")
            elif listing[-1] == "yesterday":
                Date = datetime.now() - timedelta(days=1)
                Date = Date.strftime("%Y-%m-%d")
            else:
                Date = listing[-1]
                Date = datetime.strptime(Date, "%d/%m/%Y").strftime("%Y-%m-%d")

    # Some articles are listing-dependent, so we'll search for relevant info in each
    # article.
    Property_Type = np.nan
    Bedrooms = np.nan
    Bathrooms = np.nan
    Size = np.nan
    Tenure = np.nan
    Agent = np.nan
    Agent_Long = np.nan
    Agent_Address = np.nan
    Description = np.nan

    for article in articles[2:]:
        strings = [i for i in article.stripped_strings]

        if "PROPERTY TYPE" in strings:
            Property_Type = strings[strings.index("PROPERTY TYPE") + 1]

            try:
                Bedrooms = int(strings[strings.index("BEDROOMS") + 1][1:])
            except:
                Bedrooms = np.nan
                pass

            try:
                Bathrooms = int(strings[strings.index("BATHROOMS") + 1][1:])
            except:
                Bathrooms = np.nan
                pass

            try:
                Tenure = strings[strings.index("TENURE") + 1]
            except:
                Tenure = np.nan
                pass

            try:
                Size = strings[strings.index("SIZE") + 1].replace(" sq. ft.", "")
                Size = int(Size.replace(",", ""))
            except:
                Size = np.nan
                pass

        elif "About the agent" in strings:
            # Full agent name, including any optional description
            Agent_Long = strings[1]
            Agent = Agent_Long.split(",")[0]
            Agent_Address = strings[2]
            Agent_Address = Agent_Address.replace("\r", "")
            Agent_Address = Agent_Address.replace("\n", " ")

        elif "About the development" in strings:
            # Full developer name, including any optional description
            Agent_Long = strings[1]
            Agent = strings[1]
            Agent_Address = strings[2]

            # If they haven't provided an outcode, likely the agent is in
            # the same
            #
            # Edit: I'm challenging that assumption and commenting out this
            # code for now
            #
            # if pd.isnull(Outcode):
            #     try:
            #         Outcode = re.findall("[A-Z]{1,2}[0-9][A-Z0-9]?", Agent_Address)[0]
            #     except:
            #         Outcode = np.nan

        elif "Property description" in strings:
            Description = " ".join(
                [i for i in strings[2 : strings.index("Read more") - 1]]
            )

    row = {
        "id": id,
        "Address": Address,
        "Outcode": Outcode,
        "Postcode": Postcode,
        "Price": Price,
        "Price_Qualifier": Price_Qualifier,
        "Listing_Type": Listing_Type,
        "Date": Date,
        "Property_Type": Property_Type,
        "Bedrooms": Bedrooms,
        "Bathrooms": Bathrooms,
        "Size": Size,
        "Tenure": Tenure,
        "Agent": Agent,
        "Agent_Long": Agent_Long,
        "Agent_Address": Agent_Address,
        "Description": Description,
    }

    return row


@task(log_prints=True)
def clean(rows_list: list) -> pd.DataFrame:
    """Takes a list of property row dictionaries, returns a dataframe with a correct schema.
    Depends on dtypes.yaml."""

    df = pd.DataFrame(rows_list)
    with open("./dtypes.yaml", "rb") as schema_yaml:
        schema = safe_load(schema_yaml)["rm_dtypes"]

    try:
        df = df.astype(schema)
    except BaseException as error:
        today = datetime.today().strftime("%Y-%m-%d")
        df.to_csv(f"/tmp/{today}_failed.csv")
        gcs_block = GcsBucket.load("real-estate-data")
        gcs_block.upload_from_path(
            from_path=f"/tmp/{today}_failed.csv",
            to_path=f"rm_data/failed/{today}_daily_london_failed.csv",
        )
        raise error

    return df


@task(log_prints=True, retries=3)
def save_to_gcp(df: pd.DataFrame, today: str, is_testrun: bool) -> None:
    """Takes a Pandas DataFrame, saves to GCP in Parquet format."""

    df.to_parquet(f"/tmp/{today}.parquet", engine="pyarrow")
    gcs_block = GcsBucket.load("real-estate-data")

    if is_testrun == True:
        gcs_block.upload_from_path(
            from_path=f"/tmp/{today}.parquet",
            to_path=f"rm_data/test/{today}.parquet",
        )

    gcs_block.upload_from_path(
        from_path=f"/tmp/{today}.parquet",
        to_path=f"rm_data/london_daily/{today}.parquet",
    )
    os.remove(f"/tmp/{today}.parquet")


@flow(name="Ingest Flow", log_prints=True)
def main(wait: int = 5, is_testrun: bool = True):

    today = datetime.today().strftime("%Y-%m-%d")

    if is_testrun == False:
        t = random.uniform(0, 1800)
        print(f"Sleeping {t/60:.2f} minutes")
        time.sleep(t)

    url = get_rightmove_url()
    properties_list = get_rightmove_results(url, is_testrun)

    print(f"{len(properties_list)} results found")

    rows_list = []
    for index, item in enumerate(properties_list):
        result_dict = scrape_page(item)
        rows_list.append(result_dict)

        # Rate limiting
        t_lower = wait * 0.5
        t_upper = wait * 1.5
        t = random.uniform(t_lower, t_upper)
        if index % 100 == 0 and index != 0:
            t = t * 10
        print(f"Sleeping {t:.2f} seconds")
        time.sleep(t)

    df = clean(rows_list)
    save_to_gcp(df, today, is_testrun)


if __name__ == "__main__":
    main(wait=2, is_testrun=True)

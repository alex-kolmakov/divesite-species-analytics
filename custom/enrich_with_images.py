import nest_asyncio
import urllib
import asyncio
import aiohttp
import pandas as pd

if 'custom' not in globals():
    from mage_ai.data_preparation.decorators import custom

nest_asyncio.apply()

GBIF_URL="https://api.gbif.org/v1/occurrence/search"

async def get_first_media_image(session, species_name):
    """Fetches the first image URL for a given species from the GBIF API."""

    encoded_species_name = urllib.parse.quote(species_name)
    url = f"{GBIF_URL}?q={encoded_species_name}&mediaType=StillImage&limit=1"

    try:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()

                if (
                    data['count'] > 0 and 
                    data['results'] and  # Check if 'results' list exists
                    'media' in data['results'][0]
                ):
                    media = data['results'][0]['media']        
                    return media[0]['identifier']  

    except (aiohttp.ClientConnectorError, KeyError) as e:
        pass

    return None

@custom
def enrich_invasive_with_images(df, *args, **kwargs):
    """Transforms the DataFrame, fetching images asynchronously."""

    async def fetch_image_and_update(index, row):
        async with aiohttp.ClientSession() as session:
            image_url = await get_first_media_image(session, row['scientificName'])
            return index, image_url

    async def update_dataframe():
        tasks = [fetch_image_and_update(index, row) for index, row in df.iterrows()]
        results = await asyncio.gather(*tasks)
        for index, image_url in results:
            df.at[index, 'imageUrl'] = image_url

    loop = asyncio.get_event_loop()
    loop.run_until_complete(update_dataframe())

    df = df.drop(columns=['source'])
    return df

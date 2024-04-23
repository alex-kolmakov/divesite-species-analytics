import os
import nest_asyncio
import asyncio
import aiohttp
import pandas as pd

if 'custom' not in globals():
    from mage_ai.data_preparation.decorators import custom

nest_asyncio.apply()

BASE_GUIDE_URL = os.environ.get("BASE_PADI_GUIDE_URL")
BASE_MAP_URL = os.environ.get("BASE_PADI_MAP_URL")


async def fetch_data(session, url, datakey=None):
    """Fetches data from a URL and extracts a subkey if specified."""
    async with session.get(url) as response:
        data = await response.json()
        return response.status, data[datakey] if datakey and datakey in data else data


async def fetch_all_guide_data(session):
    """Fetches dive guide data paginated across multiple requests."""
    all_data = []
    page = 1
    while True:
        url = f"{BASE_GUIDE_URL}?page={page}&page_size=1000"
        status, data = await fetch_data(session, url, datakey='results')
        if status == 404 or not data:
            break
        print(f"Successfully fetched {url}")
        all_data.extend(data)
        page += 1
    return all_data


async def fetch_map_data(session, top_right, bottom_left):
    """Fetches map data for a specific map segment."""
    url = f"{BASE_MAP_URL}?top_right={top_right}&bottom_left={bottom_left}"
    return await fetch_data(session, url)


async def get_divesites():
    """Orchestrates the main data collection process."""
    lat_size = 20
    lon_size = 20

    async with aiohttp.ClientSession() as session:
        guide_data = await fetch_all_guide_data(session)

        segments = [
            (f"{lat+lat_size},{lon+lon_size}", f"{lat},{lon}") 
            for lat in range(-90, 90, lat_size) 
            for lon in range(-340, 340, lon_size)
        ]
        print(f"Segments to go through - {len(segments)}")

        map_tasks = [fetch_map_data(session, *segment) for segment in segments]
        map_results = await asyncio.gather(*map_tasks)

        return merge_data(guide_data, map_results)


def merge_data(guide_data, map_results):
    """Combines data from the guide and map sources."""
    all_data = {}
    for map_status, map_data in map_results:
        for item in map_data:
            all_data.setdefault(item['id'], {}).update(item)

    for item in guide_data:
        all_data.setdefault(item['id'], {}).update(item)

    return all_data


@custom
def fetch_guide_data(*args, **kwargs):
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(get_divesites())
    return pd.DataFrame.from_dict(result, orient='index')

@test
def test_output(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, 'The output is undefined'
import asyncio
import os
from typing import Any

import aiohttp
import nest_asyncio
import pandas as pd

if "custom" not in globals():
    from mage_ai.data_preparation.decorators import custom, test

BASE_GUIDE_URL: str | None = os.environ.get("BASE_PADI_GUIDE_URL")
BASE_MAP_URL: str | None = os.environ.get("BASE_PADI_MAP_URL")

nest_asyncio.apply()


async def fetch_data(session: aiohttp.ClientSession, url: str, datakey: str | None = None) -> tuple[int, Any]:
    """Fetches data from a URL and extracts a subkey if specified."""
    async with session.get(url) as response:
        data = await response.json()
        return response.status, data[datakey] if datakey and datakey in data else data


async def fetch_all_guide_data(session: aiohttp.ClientSession) -> list[dict[str, Any]]:
    """Fetches dive guide data paginated across multiple requests."""
    all_data: list[dict[str, Any]] = []
    page = 1
    while True:
        url = f"{BASE_GUIDE_URL}?page={page}&page_size=1000"
        status, data = await fetch_data(session, url, datakey="results")
        if status == 404 or not data:
            break
        print(f"Successfully fetched {url}")
        all_data.extend(data)
        page += 1
    return all_data


async def fetch_map_data(session: aiohttp.ClientSession, top_right: int, bottom_left: int) -> tuple[int, Any]:

    url = f"{BASE_MAP_URL}?top_right={top_right}&bottom_left={bottom_left}"
    return await fetch_data(session, url)


async def get_divesites() -> dict[int, dict[str, Any]]:

    lat_size = 20
    lon_size = 20

    async with aiohttp.ClientSession() as session:
        guide_data = await fetch_all_guide_data(session)

        segments = [
            (f"{lat + lat_size},{lon + lon_size}", f"{lat},{lon}")
            for lat in range(-90, 90, lat_size)
            for lon in range(-340, 340, lon_size)
        ]
        print(f"Segments to go through - {len(segments)}")

        map_tasks = [fetch_map_data(session, *segment) for segment in segments]
        map_results = await asyncio.gather(*map_tasks)

        return merge_data(guide_data, map_results)


def merge_data(
    guide_data: list[dict[str, Any]], map_results: list[tuple[int, list[dict[str, Any]]]]
) -> dict[int, dict[str, Any]]:

    map_df_list = []

    for _, data in map_results:
        if isinstance(data, list):
            map_df_list.extend(data)

    map_df = pd.DataFrame(map_df_list)
    guide_df = pd.DataFrame(guide_data)

    merged_df = pd.merge(map_df, guide_df, on="id", how="outer")  # 'outer' to keep all IDs
    return merged_df.to_dict(orient="index")


@custom
def fetch_guide_data(*args: Any, **kwargs: Any) -> pd.DataFrame:

    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(get_divesites())
    return pd.DataFrame.from_dict(result, orient="index")


@test
def test_output(output: pd.DataFrame, *args: Any) -> None:
    assert output is not None, "The output is undefined"
    expected_columns = ["id", "latitude", "longitude", "title"]
    assert all(col in output.columns for col in expected_columns), (
        f"Missing expected columns: {[col for col in expected_columns if col not in output.columns]}"
    )
    assert output["id"].dtype == "int64", f"Expected 'id' column to be int64, but got {output['id'].dtype}"
    assert output["latitude"].dtype == "float64", (
        f"Expected 'latitude' column to be float64, but got {output['latitude'].dtype}"
    )
    assert not output["id"].isnull().any(), "'id' column should not have null values"
    assert (output["latitude"] >= -90).all() and (output["latitude"] <= 90).all(), (
        "Latitude values are out of the expected range"
    )
    assert (output["longitude"] >= -180).all() and (output["longitude"] <= 180).all(), (
        "Longitude values are out of the expected range"
    )

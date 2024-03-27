import io
import requests
import pandas as pd
if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


def fetch_data(url, datakey=None):
    response = requests.get(url)
    print(f"Fetched {url} with status {response.status_code}")
    data = response.json()
    if datakey and datakey in data:
        data = data[datakey]
    return response.status_code, data

def fetch_guide_data(base_url):
    page = 1
    all_data = []
    while True:
        url = f"{base_url}?page={page}&page_size=1000"
        status, data = fetch_data(url, datakey='results')
        if status == 404 or not data:
            break
        all_data.extend(data)
        page += 1
    return all_data

def load_data_from_padi():
    # Define UAE segment (adjust coordinates if needed)
    uae_top_right = '28, 57'  # Example: Approximate top-right of UAE
    uae_bottom_left = '22, 51'  # Example: Approximate bottom-left of UAE

    # Fetch guide data (no changes needed here)
    guide_base_url = "https://travel.padi.com/api/v2/travel/dive-guide/world/all/dive-sites/"
    guide_data = fetch_guide_data(guide_base_url)

    # Fetch map data for the UAE segment
    url = f"https://travel.padi.com/api/v2/travel/dsl/dive-sites/map/?top_right={uae_top_right}&bottom_left={uae_bottom_left}"
    status, map_data = fetch_data(url)

    # Combining data into a single dictionary by ID
    all_data = {}
    for item in map_data:
        if item['id'] in all_data:
            all_data[item['id']].update(item)
        else:
            all_data[item['id']] = item
    for item in guide_data:
        if item['id'] in all_data:
            all_data[item['id']].update(item)
        else:
            all_data[item['id']] = item

    # Convert the dictionary to a pandas DataFrame
    df = pd.DataFrame.from_dict(all_data, orient='index')
    return df


@data_loader
def load_data_from_api(*args, **kwargs):
    """
    Template for loading data from API
    """

    return load_data_from_padi()


@test
def test_output(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, 'The output is undefined'

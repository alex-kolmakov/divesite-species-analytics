import requests
import os
from pathlib import Path

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test



def download_file(url, destination):
    """
    Downloads a file from a given URL in chunks and saves it to the specified destination.
    """
    with requests.get(url, stream=True) as response:
        response.raise_for_status()
        
        with open(destination, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024*1024):
                f.write(chunk)
    print(f"File downloaded successfully: {destination}")



@data_loader
def load_data(**kwargs):

    url = "https://obis-datasets.ams3.digitaloceanspaces.com/exports/obis_20231025.parquet"
    destination = "obis.parquet"

    if not os.path.exists(destination):
        download_file(url, destination)

    return destination


@test
def test_output(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, 'The output is undefined'

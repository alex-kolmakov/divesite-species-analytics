import requests
import shutil
import os
from pathlib import Path

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test



def download_file(url, destination):
    with requests.get(url, stream=True) as r:
        with open(destination, 'wb') as f:
            shutil.copyfileobj(r.raw, f)

    return destination



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

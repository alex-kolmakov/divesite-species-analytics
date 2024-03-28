import urllib.request
import os
if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


@data_loader
def load_data(**kwargs):


    # Define the URL and the download path
    url = "https://obis-datasets.ams3.digitaloceanspaces.com/exports/obis_20231025.parquet"
    download_path = "obis_20231025.parquet"

    # Check if the file already exists, if not, download it
    if not os.path.exists(download_path):
        urllib.request.urlretrieve(url, download_path)
    # Specify your data loading logic here

    return download_path


@test
def test_output(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, 'The output is undefined'

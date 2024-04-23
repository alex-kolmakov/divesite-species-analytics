import io
import pandas as pd
import requests
from dwca.read import DwCAReader
if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


invasive_archive = "https://hosted-datasets.gbif.org/datasets/gisd_2011-11-20.zip"

def download_zip(url, save_path):
    response = requests.get(url, stream=True)
    with open(save_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)



@data_loader
def load_data_from_api(*args, **kwargs):
    download_zip(invasive_archive, "invasive_core_archive.zip")

    with DwCAReader("invasive_core_archive.zip") as dwca:
        print("Core data file is: {}".format(dwca.descriptor.core.file_location))

        invasive_df = dwca.pd_read(dwca.descriptor.core.file_location, parse_dates=True)
        return invasive_df


@test
def test_dataframe(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, 'The output is undefined'
    assert output.empty is not True, 'Resulting dataframe is empty'


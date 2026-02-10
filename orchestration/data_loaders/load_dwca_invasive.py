import os
import pandas as pd

from utils.download import download

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


@data_loader
def download_file(*args, **kwargs):
    url = kwargs.get('ENV_URL_TO_DOWNLOAD')
    downloaded_filename = kwargs.get('DOWNLOADED_FILENAME')
    download(url, downloaded_filename, chunk_size=8192)
    return downloaded_filename


@test
def test_dataframe(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, 'The output is undefined'
    assert os.path.exists(output), 'File does not exist after download'
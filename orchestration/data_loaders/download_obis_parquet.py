import os
import pandas as pd

from utils.download import download

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


@data_loader
def download_file(*args, **kwargs):
    downloaded_filename = kwargs.get('DOWNLOADED_FILENAME')
    if not os.path.exists(downloaded_filename):
        url = os.environ.get(kwargs.get('ENV_URL_TO_DOWNLOAD'))
        download(
            url, 
            downloaded_filename, 
            chunk_size=4098,
            update_threshold=1024*1024*1024
        )
    return downloaded_filename


@test
def test_file(output, *args) -> None:
    assert output is not None, 'The output is undefined'
    assert os.path.exists(output), 'File was not downloaded'


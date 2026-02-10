import os
from datetime import datetime

from utils.download import download

if "data_loader" not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if "test" not in globals():
    from mage_ai.data_preparation.decorators import test


@data_loader
def download_file(*args, **kwargs):
    url = os.environ.get(kwargs.get("ENV_URL_TO_DOWNLOAD"))
    url = url.replace("{year}", str(datetime.now().year)).replace("{full_date}", datetime.now().strftime("%Y-%m-01"))
    downloaded_filename = kwargs.get("DOWNLOADED_FILENAME")

    auth = None
    auth_user = os.getenv(kwargs.get("DOWNLOAD_AUTH_USER"))
    auth_password = os.getenv(kwargs.get("DOWNLOAD_AUTH_PASSWORD"))
    if auth_user and auth_password:
        auth = (auth_user, auth_password)

    download(url, downloaded_filename, auth=auth, chunk_size=8192)
    return downloaded_filename


@test
def test_dataframe(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, "The output is undefined"
    assert os.path.exists(output), "File was not downloaded"

import os
import pandas as pd
from dwca.read import DwCAReader

from utils.download_zip import download_zip
if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


redlist_archive = os.environ.get("REDLIST_DWCA_ARCHIVE")


@data_loader
def load_data_from_api(*args, **kwargs):
    download_zip(redlist_archive, "redlist_core_archive.zip")

    with DwCAReader("redlist_core_archive.zip") as dwca:
        print("Core data file is: {}".format(dwca.descriptor.core.file_location))

        redlist_df = dwca.pd_read(dwca.descriptor.core.file_location, parse_dates=True)
        return redlist_df


@test
def test_dataframe(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, 'The output is undefined'
    assert output.empty is not True, 'Resulting dataframe is empty'


from dwca.read import DwCAReader
if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


@transformer
def parse_invasive_dwca(data, *args, **kwargs):
    """
    Convert DwCA into a dataframe.

    Args:
        data: Zip filename with proper DwCA inside
        args: The output from any additional upstream blocks (if applicable)

    Returns:
        Dataframe
    """
    with DwCAReader(kwargs.get("DOWNLOADED_FILENAME")) as dwca:
        print("Core data file is: {}".format(dwca.descriptor.core.file_location))

        dataframe = dwca.pd_read(dwca.descriptor.core.file_location, parse_dates=True)

        return dataframe


@test
def test_output(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, 'The output is undefined'
    assert output.empty is False, 'Resulting dataframe is empty.'
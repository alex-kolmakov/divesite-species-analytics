from dwca.read import DwCAReader

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


@transformer
def parse_dwca(data, *args, **kwargs):

    with DwCAReader(kwargs.get("DOWNLOADED_FILENAME")) as dwca:
        print("Core data file is: {}".format(dwca.descriptor.core.file_location))

        dataframe = dwca.pd_read(dwca.descriptor.core.file_location, parse_dates=True)

        if kwargs.get('REMOVE_DUPLICATE_AUTHORS'):
            dataframe = dataframe.dropna(subset=["scientificNameAuthorship"])
            dataframe['scientificName'] = dataframe.apply(
                lambda row: row['scientificName'].replace(row['scientificNameAuthorship'], ''
            ).strip(), axis=1)

        return dataframe


@test
def test_output(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, 'The output is undefined'
    assert output.empty is not True, 'Resulting dataframe is empty'

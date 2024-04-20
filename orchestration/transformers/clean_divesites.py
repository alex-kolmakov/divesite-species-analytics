if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


@transformer
def transform(divesites_dataframe, *args, **kwargs):

    df = divesites_dataframe.dropna(subset=['latitude', 'longitude', 'title'])
    df = df.drop(columns=['images'])
    return df


@test
def test_output(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, 'The output is undefined'

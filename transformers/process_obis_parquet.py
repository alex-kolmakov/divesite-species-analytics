import pandas as pd
import pyspark
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .master("local[*]") \
    .appName('test') \
    .config("spark.executor.memory", "10g") \
    .config("spark.driver.memory", "10g") \
    .config("spark.memory.offHeap.enabled", "true") \
    .config("spark.memory.offHeap.size","16g") \
    .getOrCreate()

pd.set_option('display.max_columns', 500)

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


@transformer
def transform(obis_parquet, *args, **kwargs):

    df = spark.read \
        .parquet(obis_parquet)


    return df


@test
def test_output(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, 'The output is undefined'

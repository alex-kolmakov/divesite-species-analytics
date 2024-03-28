if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test
import pandas as pd
import pyspark
from pyspark.sql import SparkSession

@transformer
def transform(data, *args, **kwargs):
    spark = kwargs.get('spark')
    spark_conf = spark.sparkContext._conf.setAll([
        ('spark.executor.memory', '1g'), 
        ('spark.app.name', 'Spark Updated Conf'), 
        ('spark.executor.cores', '1'), 
        ('spark.cores.max', '1'), 
        ('spark.driver.memory','1g'),
        ("spark.sql.shuffle.partitions", "300"),
        ("spark.sql.files.maxPartitionBytes", "128m")])
    df = spark.read.parquet(data).repartition(300)
    obis_columns = ["marine", "class", "genus", "species", "variety", "individualCount", "eventDate", "eventTime", "year", "month", "day", "country", "locality", "decimalLongitude", "decimalLatitude"]

    obis_df = df.select(obis_columns)
    obis_df.coalesce(1).write.parquet("obis.parquet")
    return "obis.parquet"


@test
def test_output(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, 'The output is undefined'

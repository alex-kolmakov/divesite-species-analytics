import pyspark
import os
from pyspark.sql import functions as F
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, FloatType

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


spark = SparkSession.builder \
    .master(os.environ.get('SPARK_MASTER_HOST')) \
    .appName('OBIS') \
    .config("spark.executor.memory", "1g") \
    .config("spark.driver.memory", "4g") \
    .config("spark.sql.files.maxPartitionBytes", "128m") \
    .getOrCreate()


@transformer
def transform(data, *args, **kwargs):
    obis_columns = [
        "species", "individualCount", "eventDate", "eventTime",
        "year", "month", "day", "decimalLongitude", "decimalLatitude"
    ]
    # Define the schema
    obis_schema = StructType([
        StructField("species", StringType(), True),
        StructField("individualCount", StringType(), True), # we have almost anything there even Binary
        StructField("eventDate", StringType(), True),
        StructField("eventTime", StringType(), True),
        StructField("year", StringType(), True),
        StructField("month", StringType(), True),
        StructField("day", StringType(), True),
        StructField("decimalLongitude", FloatType(), True),
        StructField("decimalLatitude", FloatType(), True)
    ])

    # Read the parquet file with the defined schema
    df = spark.read.schema(obis_schema).parquet("/home/data/obis.parquet")

    current_year = datetime.now().year

    obis_df = df.select(
        "species", "eventDate", "eventTime",
        "decimalLongitude", "decimalLatitude",
        F.col("year").cast(IntegerType()),
        F.col("month").cast(IntegerType()),
        F.col("day").cast(IntegerType()),
        F.col("individualCount").cast(IntegerType()),
    )

    # Filtering the DataFrame
    filtered_df = obis_df.filter(
        (F.col('species').isNotNull()) &
        (F.col('eventDate').isNotNull()) &
        (F.col('individualCount').isNotNull()) &
        (F.col('individualCount') > 0) & 
        (F.col('month') > 0) &
        (F.col('day') > 0) &
        (F.col('year') >= current_year - 15) # because after 2008 data becomes too malformed to be interpreted by spark easily
    )

    obis_df = filtered_df.toPandas()

    return obis_df

@test
def test_output(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, 'The output is undefined'

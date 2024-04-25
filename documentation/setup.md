
## Prerequisites

- Docker & Docker compose
- Google Cloud SDK (for interacting with Google Cloud Storage through terraform)
- Terraform
- Preferrably access to Google Cloud Platform and Virtual Machine with at least 4 vCPUs and 10GB of RAM and 70GB of disk space and good download speed (we will be struggling with unpartitioned 20GB parquet).



## Setup

1. Clone the repository:

```sh
git clone https://github.com/yourusername/marine-species-analytics.git && cd marine-species-analytics
```


2. Create a `secret.json` file with your Google Cloud credentials from Service Account and put it in the root of the project.

3. Update variables inside `variables.tf` to match your project setup in Google Cloud.

4. Configure your Google Cloud SDK:

```sh
gcloud init
```

5. Run `terraform apply` to get all resources in the cloud up and running.


6. Before starting the project you would need to populate `.env` file. Use `.env.sample` as a template.
Environment variables are:
    -   `SPARK_MASTER_HOST` host selected for Spark master, if at some poing standalone Spark cluster will not be enough and you would like to use more performant option.

    -   `AGGREGATION_WINDOW_DAYS: 1095` - number of days. Occurence data for the past 3 years will be used by default.
    -   `PROXIMITY_METERS: 1000` - occurence points deemed "near" the divesites location when they are 1 kilometer or closer.
    -   `LATTITUDE_TOP: 26.5`
    -   `LATTITUDE_BOTTOM: 22.5`
    -   `LONGITUDE_LEFT: 51`
    -   `LONGITUDE_RIGHT: 56.5`  - all these variables allow you to pick a "square" on the map by pointing to top-right and bottom-left corners of the map. Default values represent south-eastern part of the Persian Gulf encompassing UAE.


7. Run the compose file to start mage.ai:

```sh
docker-compose up --build -d
```

9. After this - proceed to port 6789 and launch the pipeline or setup a trigger.


## WARNING

Launching pipeline combines both GBIF and OBIS datasets and consumes around 130GiB in processed data from BigQuery. This happens because of the filtering over geographic coordinates in the `stg_occurences.sql` model.
<img width="1319" alt="Screenshot 2024-03-29 at 6 19 32 PM" src="https://github.com/Feanaur/marine-species-analytics/assets/3127175/ac1fd75f-46dc-4ca1-a261-dd3197fc7eb0">

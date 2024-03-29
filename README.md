# Marine Species Analytics

This project uses mage.ai to orchestrate data ingestion and dbt runs for a marine species analytics project. The data ingestion script fetches data from the web and stores it in Google Cloud Storage. The dbt models transform the raw data into a structured format that can be used for analysis.

## Prerequisites

- Docker & Docker compose
- Google Cloud SDK (for interacting with Google Cloud Storage through terraform)
- Terraform
- Jupyter Notebook & Spark (To be automated in the future)

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


6. MANUAL STEP: run locally `obis_data.ipynb` to get the data from OBIS API and save it. For this you will need to have Jupyter Notebook installed in your local machine with access to local Spark Cluster(or any other of your choice). Once you have the data, you can upload it to Google Cloud Storage. This step is not automated in the pipeline and will be the focus of later improvements.


7. Run the compose file to start mage.ai:

```sh
docker-compose up --build -d
```

8. After this - proceed to port 6789 and launch the pipeline or setup a trigger.


## WARNING

Launching pipeline combines both GBIF and OBIS datasets and consumes around 130GiB in processed data from BigQuery. This happens because of the filtering over geographic coordinates in the `stg_occurences.sql` model.
<img width="1319" alt="Screenshot 2024-03-29 at 6 19 32 PM" src="https://github.com/Feanaur/marine-species-analytics/assets/3127175/ac1fd75f-46dc-4ca1-a261-dd3197fc7eb0">

## Models preview

Orchestration tree
<img width="990" alt="Screenshot 2024-03-29 at 6 16 36 PM" src="https://github.com/Feanaur/marine-species-analytics/assets/3127175/ae09b781-42a7-41cc-9ae5-75a4cdd08179">

DBT models
<img width="1419" alt="Screenshot 2024-03-29 at 6 14 34 PM" src="https://github.com/Feanaur/marine-species-analytics/assets/3127175/d20bd13a-f887-4436-86d9-7d245a4cff8b">





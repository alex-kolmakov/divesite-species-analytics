
# Divesite Species Analytics Data Pipeline 

### Data Engineering Zoom Camp | 2024 Cohort | Capstone Project 

_**Author | Aleksandr Kolmakov**_



## Table of Contents


  <a href="#problem-statement">Problem Statement</a> • 
  <a href="#applied-tools--technologies">Applied Tools & Technologies</a> •
  <a href="#architecture-diagram">Architecture Diagram</a> • 
  <a href="#articles">Articles</a> • 
  <a href="#terraform-infrastructure-as-code">Terraform Infrastructure as Code</a> •

  <a href="#testing">Testing</a> •
  <a href="#dashboard">Dashboard</a> •
  <a href="#further-ideas--next-steps">Further Ideas & Next Steps</a> •
  <a href="#licensing">Licensing</a> •
  <a href="#contributing--support">Contributing & Support</a> •
  <a href="#acknowledgements--credits">Acknowledgements & Credits</a>


### _Problem Statement_

Efficiently collecting, processing, and disseminating critical earthquake information is imperative due to global seismic activity's varying magnitudes and frequencies. There's a pressing need to streamline earthquake data management for timely analysis, decision-making, and response efforts across the globe.


### _Articles_ 

Project is described in depth on the following articles:
  - [Data Engineering Zoom Camp | Capstone Project](https://www.linkedin.com/pulse/data-engineering-zoom-camp-capstone-project-aleksandr-kolmakov/)


### _Applied Tools & Technologies_

Containerisation: <a href="https://www.docker.com/">Docker</a><br>
Workflow Orchestration: <a href="https://www.mage.ai/">Mage</a><br>
Data Transformations: <a href="https://www.getdbt.com/">DBT</a><br>
Compute Engine: <a href="https://cloud.google.com/products/compute?hl=en">Google Cloud Virtual Machine</a><br>
Data Lake: <a href="https://cloud.google.com/storage/?hl=en">Google Cloud Storage</a><br>
Data Warehouse: <a href="https://cloud.google.com/bigquery?hl=en">Google BigQuery</a><br>
Infrastructure as Code (IaC): <a href="https://www.terraform.io/">Terraform</a><br>
Visualisation: <a href="https://lookerstudio.google.com/">Looker Studio</a><br>





This project uses 4 sources of data: 
- [GBIF occurence data](https://www.gbif.org/)
- [OBIS data as additional source of occurence data](https://obis.org/)
- [Global invasive species database](https://www.gbif.org/dataset/b351a324-77c4-41c9-a909-f30f77268bc4)
- [IUCN Red list of species as a Darwin Core archive](https://www.gbif.org/dataset/19491596-35ae-4a91-9a98-85cf505f1bd3)

Combining them will allow to explain how different underwater points of interest relate to occurence data.


<img width="1253" alt="Screenshot 2024-04-23 at 2 15 41 PM" src="https://github.com/Feanaur/divesite-species-analytics/assets/3127175/7bcb7d82-53bc-4dbc-8da4-b08fb1ec846a">



This project uses mage.ai to orchestrate data ingestion and dbt runs for a marine species analytics project. The data ingestion script fetches data from the web and stores it in Google Cloud Storage. The dbt models transform the raw data into a structured format that can be used for analysis.


## Models preview

Orchestration tree
<img width="990" alt="Screenshot 2024-03-29 at 6 16 36 PM" src="https://github.com/Feanaur/marine-species-analytics/assets/3127175/ae09b781-42a7-41cc-9ae5-75a4cdd08179">

DBT models
<img width="1419" alt="Screenshot 2024-03-29 at 6 14 34 PM" src="https://github.com/Feanaur/marine-species-analytics/assets/3127175/d20bd13a-f887-4436-86d9-7d245a4cff8b">



## Dashboard

[Dashboard](https://lookerstudio.google.com/s/vSQv3DXuGNQ) was done in Looker Studio and has 3 pages:
- Divesites view
- Invasive species near divesites view
- Endangered species near divesites view 



## Improvements

- OBIS data proved to be challenging as it is offered as single files weighing more than 15Gb. Due to time constraints processing of that wont be included in the orchestrated pipeline - but for convenience already provided as a Pyspark notebook that will produce required result locally and allow for upload to GCS. For the second iteration it will be beneficial to add this to overall pipeline or make it a standalone pipeline running on a PySpark kernel.

- There is a way to enrich the data with adding images to species by either feeding them through gbif api or implementing custom search endpoints on google. But it will require to make mage node asynchronous since doing this normally takes much longer.

- Final improvement will be adding ability to mix in community observed data either through common tables and forms or any other to make the data even more relatable.

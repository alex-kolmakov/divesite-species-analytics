
# Divesite Species Analytics Data Pipeline 

### Data Engineering Zoom Camp | 2024 Cohort | Capstone Project 

_**Author | Aleksandr Kolmakov**_



## Table of Contents
<a href="#articles">Articles</a> • 
<a href="#applied-tools--technologies">Applied Tools & Technologies</a> •
<a href="#architecture-diagram">Architecture Diagram</a> • 
<a href="#terraform-infrastructure-as-code">Terraform Infrastructure as Code</a> •
<a href="#testing">Testing</a> •
<a href="#dashboard">Dashboard</a> •
<a href="#further-ideas--next-steps">Further Ideas & Next Steps</a> •
<a href="#licensing">Licensing</a> •
<a href="#contributing--support">Contributing & Support</a> •
<a href="#acknowledgements--credits">Acknowledgements & Credits</a>


### _Articles_ 

Project is described in depth on the following articles:
  - [Data Engineering Zoom Camp | Capstone Project](https://www.linkedin.com/pulse/data-engineering-zoom-camp-capstone-project-aleksandr-kolmakov/)


### _Applied Tools & Technologies_
<div align="center">
  <a href="https://www.docker.com/">Docker</a> • <a href="https://www.mage.ai/">Mage</a> • <a href="https://spark.apache.org/">Spark</a> • <a href="https://cloud.google.com/products/compute?hl=en">Google Cloud Virtual Machine</a> • <a href="https://cloud.google.com/storage/?hl=en">Google Cloud Storage</a> • <a href="https://cloud.google.com/bigquery?hl=en">Google BigQuery</a> • <a href="https://www.terraform.io/">Terraform</a> • <a href="https://lookerstudio.google.com/">Looker Studio</a>
</div>



### Project Folder Structure
```bash
.
├── README.md                    -- this file                
├── Dockerfile                   -- file to use for building a Docker image
├── /apps                        -- folder for deployment, used by Dockerfile
    ├── home.py                  -- entrypoint of streamlit web-service
    ├── /pages                   -- folder for sites' subpages
        ├── about.py             -- an about me page
        ├── dv.bin               -- the processed and scaled data DictVectorizer
        ├── model.bin            -- the final model used in web app  
        ├── eda.py               -- samples of EDA done
        ├── predict.py           -- the heart of the project
├── /artifacts                   -- folder for images and other artifacts
                                    used in this report and this project
├── /data                        -- houses data file(s)  
├── /src                         -- project's python scripts
    ├── config.py                -- global constants
    ├── clf_catboost.py          -- code to produce catboost.bin
    ├── clf_histboost.py         -- code to produce model.bin 
                                   (output then moved to /app/pages)
    ├── data_loader.py           -- code to read data files
    ├── data_preprocessor.py     -- code to handle preprocessing of data
    ├── data_feature_builder.py  -- code to create new features
    ├── modeler.py               -- code related to models
    ├── predict.py               -- code to test flask app locally
    ├── predict_test.py          -- code to test flask web-service locally

```



This project uses 4 sources of data: 
- [GBIF occurence data](https://www.gbif.org/)
- [OBIS data as additional source of occurence data](https://obis.org/)
- [Global invasive species database](https://www.gbif.org/dataset/b351a324-77c4-41c9-a909-f30f77268bc4)
- [IUCN Red list of species as a Darwin Core archive](https://www.gbif.org/dataset/19491596-35ae-4a91-9a98-85cf505f1bd3)

Combining them will allow to explain how different underwater points of interest relate to occurence data.


<img width="1253" alt="Screenshot 2024-04-23 at 2 15 41 PM" src="https://github.com/Feanaur/divesite-species-analytics/assets/3127175/7bcb7d82-53bc-4dbc-8da4-b08fb1ec846a">



This project uses mage.ai to orchestrate data ingestion and dbt runs for a marine species analytics project. The data ingestion script fetches data from the web and stores it in Google Cloud Storage. The dbt models transform the raw data into a structured format that can be used for analysis.


## Pipeline preview

### Data ingestion pipelines

### DBT models

## Data modelling
Schema here and then link to the article 



## Dashboard

[Dashboard](https://lookerstudio.google.com/s/vSQv3DXuGNQ) was done in Looker Studio and has 3 pages:
- Divesites view
- Invasive species near divesites view
- Endangered species near divesites view 



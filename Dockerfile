FROM mageai/mageai:latest

ARG MAGE_CODE_PATH=/home/src

ARG PIP=pip3

WORKDIR ${MAGE_CODE_PATH}

COPY . .

RUN ${PIP} install -r requirements.txt

RUN cd marine_data && dbt deps && cd ${MAGE_CODE_PATH}

ENV PYTHONPATH="${PYTHONPATH}:/home/src"

CMD ["/bin/sh", "-c", "/app/run_app.sh"]

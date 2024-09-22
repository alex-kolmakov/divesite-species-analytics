FROM mageai/mageai:latest
ARG PIP=pip3

ARG MAGE_CODE_PATH=/home/src

WORKDIR ${MAGE_CODE_PATH}

COPY orchestration .
COPY requirements.txt .
RUN ${PIP} install -r requirements.txt

WORKDIR ${MAGE_CODE_PATH}/orchestration

ENV PYTHONPATH="${PYTHONPATH}:/home/src"

CMD ["/bin/sh", "-c", "/app/run_app.sh"]

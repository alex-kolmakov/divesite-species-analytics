FROM mageai/mageai:latest
ARG PIP=pip3

# Add Debian Bullseye repository
RUN echo 'deb http://deb.debian.org/debian bullseye main' > /etc/apt/sources.list.d/bullseye.list

# Install OpenJDK 11
RUN apt-get update -y && \
    apt-get install -y openjdk-11-jdk

# Remove Debian Bullseye repository
RUN rm /etc/apt/sources.list.d/bullseye.list

ARG MAGE_CODE_PATH=/home/src

WORKDIR ${MAGE_CODE_PATH}

COPY orchestration .
COPY requirements.txt .
RUN ${PIP} install -r requirements.txt

WORKDIR ${MAGE_CODE_PATH}/orchestration

ENV PYTHONPATH="${PYTHONPATH}:/home/src"

CMD ["/bin/sh", "-c", "/app/run_app.sh"]

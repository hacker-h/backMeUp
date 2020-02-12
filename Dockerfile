FROM ubuntu:16.10

COPY ./requirements.txt /requirements.txt

RUN apt-get update &&\
    apt-get install -y \
    curl \
    python3 \
    python3-pip \
    zip && \
    pip3 install -r requirements.txt && \
    apt-get clean autoclean && \
    apt-get autoremove -y

# for explicity purposes
USER root

WORKDIR /mandatoryVolume

ENTRYPOINT [ "python3", "-u", "/mandatoryVolume/back_me_up.py" ]

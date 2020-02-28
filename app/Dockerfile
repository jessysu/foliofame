FROM ubuntu:16.04

RUN apt-get update && apt-get install -y software-properties-common python-software-properties && apt-get update

# Install Python Setuptools
RUN apt-get install -y python3-pip libmysqlclient-dev

# Initialize
RUN mkdir -p /data/web
WORKDIR /data/web
COPY requirements.txt /data/web/

# Setup
RUN pip3 install --upgrade pip
RUN pip3 install -r requirements.txt

# Clean

# Prepare
COPY . /data/web/
#RUN mkdir -p mydjango/static/admin

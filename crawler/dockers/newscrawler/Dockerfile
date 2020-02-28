# Using official python runtime base image
FROM ubuntu:16.04

RUN apt-get update && apt-get install -y software-properties-common python-software-properties && apt-get update

# Install Python Setuptools
RUN apt-get install -y python3-pip cron zip mysql-client

#RUN apt-get purge -y python-software-properties software-properties-common && apt-get clean -y && apt-get autoclean -y && apt-get autoremove -y && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

#RUN apt-get install libprotobuf-dev protobuf-compiler
RUN add-apt-repository "deb http://mirrors.us.kernel.org/ubuntu/ xenial main"
RUN apt-get update  && apt-get install -y libprotobuf-dev protobuf-compiler

RUN export MYSQLXPB_PROTOC=/usr/bin/protoc
RUN export MYSQLXPB_PROTOBUF_INCLUDE_DIR=/usr/include/google/protobuf
RUN export MYSQLXPB_PROTOBUF_LIB_DIR=/usr/lib/x86_64-linux-gnu

# Set the application directory
WORKDIR /app

# Install our requirements.txt
ADD requirements.txt /app/requirements.txt
RUN pip3 install -r requirements.txt

RUN pip3 install --upgrade requests

# Copy our code from the current folder to /app inside the container
ADD . /app

# Make port 80 available for links and/or publish
#EXPOSE 80

# Define our command to be run when launching the container
#CMD ["python", "/app/ff_script/get_stock_adj.py"]
# Add crontab file in the cron directory
ADD news-cron /etc/cron.d/news-cron
 
# Give execution rights on the cron job
RUN chmod 0644 /etc/cron.d/news-cron
 
# Create the log file to be able to run tail
RUN touch /var/log/cron_finnews_iex.log
 
# Run the command on container startup
#CMD cron  && tail -f /var/log/cron.log

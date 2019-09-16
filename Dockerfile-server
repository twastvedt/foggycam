FROM python:alpine
# Install.
RUN \
  apk add --update && \
  apk add  --no-cache build-base  py-pip  libffi-dev openssl-dev py-pip  && \
  pip install --upgrade pip && \
  rm -rf /var/cache/apk/* 

ADD ./src/ /apps/src
ADD ./config.json /apps/

RUN pip3 install -r /apps/src/requirements.txt
# Set environment variables.
ENV HOME /root

# Define working directory.
WORKDIR /apps/src

ENTRYPOINT ["python", "start.py"] 

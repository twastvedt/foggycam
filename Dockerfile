FROM python:alpine
# Install.
RUN \
  apk add --update && \
  apk add  --no-cache build-base py-pip libffi-dev openssl-dev && \
  pip install --upgrade pip && \
  pip install --user pipenv --no-warn-script-location && \
  rm -rf /var/cache/apk/* 

ADD ./src/ /apps/src
ADD ./config.json /apps/

# Define working directory.
WORKDIR /apps/src

RUN /root/.local/bin/pipenv install

# Set environment variables.
ENV HOME /root

ENTRYPOINT ["/root/.local/bin/pipenv", "run", "python", "startServer.py"] 

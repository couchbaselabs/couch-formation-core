FROM ubuntu:jammy as base

# Install required OS packages
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC
RUN apt-get update
RUN apt-get install -q -y python3 python3-dev python3-venv python3-pip git curl unzip apt-transport-https ca-certificates gnupg

RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-$(uname -m).zip" -o "/var/tmp/awscliv2.zip"
WORKDIR /var/tmp
RUN unzip awscliv2.zip
RUN ./aws/install

RUN curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list
RUN apt-get update
RUN apt-get install -q -y google-cloud-cli

RUN curl -sL https://aka.ms/InstallAzureCLIDeb | bash

RUN groupadd -g 1000 ubuntu
RUN useradd -u 1000 -g 1000 -ms /bin/bash ubuntu

USER ubuntu
WORKDIR /home/ubuntu

RUN mkdir -p .local/bin
RUN mkdir -p .aws
RUN mkdir -p .azure
RUN mkdir -p .config/gcloud
RUN mkdir -p .ssh
ENV PATH="/home/ubuntu/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin"

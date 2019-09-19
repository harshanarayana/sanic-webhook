# K8s Webhook Admission Controllers in Python
Kubernetes Mutating and Validating Webhooks written in Sanic

# Usage Instructions

As part of this script, there is a helper utility provided that can be leveraged to setup and get this demo running
on your cluster with almost no major effort.

Below is a series of options/actions to be performed in order to get the example app working.

## Pre Requisites

1. Python 3.7 or higher
2. `minikube`
3. `docker`

## Setup Deployment Env

```bash
# Change to pyenv or any suitable python ENV before running the following
pip install -r dev-requirements.txt
```
This will install and setup all the required components for performing the single command deployment.

## Start K8s Cluster
```bash
minikube start
```

## Generate Certificates for your own K8S Setup

We need to create a custom cert key pair and get it signed and approved using the kubernetes so that the
webhook APIs can be called by the API Server.

```bash
./deploy/deployer --mode certs --app app_name_for_your_demo
```

## Build the Docker Image with custom Certs

```bash
eval $(minikube docker-env)
docker build . -t app_name_for_your_demo:image_version
```

## Setup Minikube for Webhook Authentiation
```bash
./deploy/deployer --restart-minikube
```

## Deploying Webhook

Once the above step is complete, it will stop and restart the minikube with additional args
required to perform Authenticated Webhook request. Now you go ahead and deploy the
required setup for Webhooks.

```bash
./deploy/deployer --app app_name_for_your_demo --image app_name_for_your_demo:image_version
```

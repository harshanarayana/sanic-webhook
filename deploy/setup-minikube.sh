#!/usr/bin/env bash

SSH_KEY_FILE=$(minikube ssh-key)

scp -i ${SSH_KEY_FILE} ./admission-control-config.yaml docker@$(minikube ip):/home/docker/admission-control-config.yaml
scp -i ${SSH_KEY_FILE} ./kube-config.yaml docker@$(minikube ip):/home/docker/kube-config.yaml

read  -n 1 -p "Please run 'minikube ssh' and copy the files to right destinations and press [ENTER]: " mainmenuinput

minikube stop
minikube start --extra-config=apiserver.admission-control-config-file=/var/lib/minikube/certs/admission-control-config.yaml

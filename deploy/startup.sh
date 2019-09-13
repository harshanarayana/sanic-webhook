#!/usr/bin/env bash

kubectl create cm allowed-registries --from-file=./allowed.json

kubectl apply -f ./deployment.yaml
kubectl apply -f ./service.yaml
kubectl apply -f ./validating.yaml
kubectl apply -f ./mutating.yaml
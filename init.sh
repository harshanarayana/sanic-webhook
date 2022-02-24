#!/bin/sh

ca_bundle=$(cat /mnt/ca.crt | base64 -w0)
echo "${ca_bundle}"
sed -i "s/##CABUNDLE##/${ca_bundle}/g" /mutating.yaml
sed -i "s/##CABUNDLE##/${ca_bundle}/g" /validating.yaml
kubectl apply -f /mutating.yaml
kubectl apply -f /validating.yaml

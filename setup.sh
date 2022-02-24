#!/bin/bash
kubectl apply -f certs/cert-manager.yaml
kubectl rollout status -n cert-manager deployment/cert-manager
kubectl label ns --overwrite cert-manager ignore-admission="true"

for attemt in $(seq 1 200); do
    retry=false
    echo "Trying to create cluster issuer"
    kubectl apply -f certs/issuer.yaml 2>/dev/null
    if [[ ! "$?" = "0" ]]; then
        retry=true
    fi
    if [[ ! "${retry}" = "true" ]]; then
        exit 0
    fi
    sleep 10
done


#!/usr/bin/env bash

kubectl delete MutatingWebhookConfiguration maglev-admission-webhook
kubectl delete ValidatingWebhookConfiguration maglev-admission-webhook

kubectl delete deployment maglev-admission-webhook
kubectl delete svc maglev-admission-webhook
kubectl delete cm allowed-registries

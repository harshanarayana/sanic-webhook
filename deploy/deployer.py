#!/usr/bin/env python


from argparse import ArgumentParser
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from base64 import b64encode
from jinja2 import Environment, BaseLoader, Template
from os import path, walk
from yaml import safe_load
from datetime import datetime
from time import sleep

from subprocess import check_output
from shutil import copyfile

import logging
from pylogrus import PyLogrus, TextFormatter

logging.setLoggerClass(PyLogrus)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = TextFormatter(datefmt="Z", colorize=True)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
logger.addHandler(ch)


config.load_kube_config()

corev1_api = client.CoreV1Api(client.ApiClient())
apps_v1_api = client.AppsV1Api(client.ApiClient())
webhook_api = client.AdmissionregistrationV1beta1Api(client.ApiClient())
cert_api = client.CertificatesV1beta1Api(client.ApiClient())


APP_NAME = "maglev-admission-webhook"
SECRET = "shhhh!donottell"
NAMESPACE = "default"
CSR_NAME = "{}.{}".format(APP_NAME, NAMESPACE)

TEMPLATE_ENV = Environment(loader=BaseLoader)
RESOURCE_CREATION_MAP = {
    "Deployment": {"handler": apps_v1_api.create_namespaced_deployment},
    "Service": {"handler": corev1_api.create_namespaced_service},
    "ConfigMap": {"handler": corev1_api.create_namespaced_config_map},
    "ValidatingWebhookConfiguration": {
        "handler": webhook_api.create_validating_webhook_configuration,
        "ns_required": False,
    },
    "MutatingWebhookConfiguration": {
        "handler": webhook_api.create_mutating_webhook_configuration,
        "ns_required": False,
    },
}


NAMESPACE_REQUIRED = {""}


def ignore_404(func):
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except ApiException as ae:
            if ae.status == 404:
                pass
            else:
                raise ae

    return wrapper


def _extract_ca_bundle():
    data = corev1_api.read_namespaced_config_map(
        name="extension-apiserver-authentication", namespace="kube-system"
    )
    return b64encode(data.data["client-ca-file"].encode()).decode()


@ignore_404
def _cleanup_config_map():
    logger.info("Deleting config map for %s", APP_NAME)
    corev1_api.delete_namespaced_config_map(name=APP_NAME, namespace="default")


@ignore_404
def _cleanup_deployment():
    logger.info("Deleting deployment for %s", APP_NAME)
    apps_v1_api.delete_namespaced_deployment(name=APP_NAME, namespace="default")


@ignore_404
def _cleanup_service():
    logger.info("Deleting service for %s", APP_NAME)
    corev1_api.delete_namespaced_service(name=APP_NAME, namespace="default")


@ignore_404
def _cleanup_validating_hooks():
    logger.info("Deleting validating webhook for %s", APP_NAME)
    webhook_api.delete_validating_webhook_configuration(name=APP_NAME)


@ignore_404
def _cleanup_mutating_hooks():
    logger.info("Deleting mutating webhook for %s", APP_NAME)
    webhook_api.delete_mutating_webhook_configuration(name=APP_NAME)


@ignore_404
def _cleanup_csr():
    logger.info("Clearning up CSR for %s", CSR_NAME)
    cert_api.delete_certificate_signing_request(name=CSR_NAME)


def cleanup():
    _cleanup_mutating_hooks()
    _cleanup_validating_hooks()
    _cleanup_service()
    _cleanup_deployment()
    _cleanup_config_map()


def _openssl(*args):
    cmd = ["openssl"] + list(args)
    return check_output(cmd)


def deploy(ca_bundle):
    base_path = path.join(path.dirname(path.abspath(__file__)), "artifacts")
    for root, dirs, files in walk(base_path, topdown=True):
        for file in files:
            with open(path.join(base_path, file)) as fh:
                data = fh.read()
            template = TEMPLATE_ENV.from_string(data)  # type: Template
            rendered_data = template.render(app_name=APP_NAME, ca_bundle=ca_bundle)
            rendered_data = safe_load(rendered_data)
            processor = RESOURCE_CREATION_MAP[rendered_data["kind"]]
            logger.info("Creating %s for %s", rendered_data["kind"], APP_NAME)
            if processor.get("ns_required", True):
                processor["handler"](namespace="default", body=rendered_data)
            else:
                processor["handler"](body=rendered_data)


def build_certs():
    base_path = path.join(path.dirname(path.abspath(__file__)), "certs")
    ssl_path = path.join(
        path.dirname(path.dirname(path.abspath(__file__))),
        "ssl"
    )
    with open(path.join(base_path, "csr-conf.tpl")) as fh:
        data = fh.read()

    template = TEMPLATE_ENV.from_string(data)
    rendered_data = template.render(app_name=APP_NAME, namespace=NAMESPACE)
    with open("/tmp/csr.conf", "w") as fh:
        fh.write(rendered_data)

    logger.info("Generating RSA Key file...")
    _ = _openssl("genrsa", "-out", "/tmp/server-key.pem", "2048")

    logger.info("Generating CSR Request data...")
    _ = _openssl(
        "req",
        "-new",
        "-key",
        "/tmp/server-key.pem",
        "-subj",
        "/CN={}.{}.svc".format(APP_NAME, NAMESPACE),
        "-out",
        "/tmp/server.csr",
        "-config",
        "/tmp/csr.conf",
    )

    _cleanup_csr()

    with open("/tmp/server.csr") as fh:
        request_data = fh.read()

    with open(path.join(base_path, "csr.yaml")) as fh:
        data = fh.read()

    template = TEMPLATE_ENV.from_string(data)
    rendered_data = template.render(
        csr_name=CSR_NAME, csr_data=b64encode(request_data.encode()).decode()
    )
    rendered_data = safe_load(rendered_data)

    logger.info("Creating a CSR for %s", CSR_NAME)

    cert_api.create_certificate_signing_request(body=rendered_data)

    logger.info("Approving CSR for %s", CSR_NAME)
    approval_condition = client.V1beta1CertificateSigningRequestCondition(
        last_update_time=datetime.now().astimezone(),
        message="This certificate was approved by Python Client API",
        reason="MyOwnReason",
        type="Approved",
    )
    body = cert_api.read_certificate_signing_request_status(name=CSR_NAME)
    body.status.conditions = [approval_condition]
    cert_api.replace_certificate_signing_request_approval(name=CSR_NAME, body=body)

    for attempt in range(10):
        logger.info(
            "[Attempt %d] Checking if the CSR for %s is approved", attempt, CSR_NAME
        )
        csr_data = cert_api.read_certificate_signing_request(name=CSR_NAME)
        logger.info(csr_data.status.certificate)
        if csr_data.status.certificate:
            with open("/tmp/cert.data", "w") as fh:
                fh.write(csr_data.status.certificate)

            _ = _openssl(
                "base64",
                "-d",
                "-A",
                "-out",
                "/tmp/server-cert.pem",
                "-in",
                "/tmp/cert.data"
            )
            break
        else:
            sleep(1)
    else:
        logger.error("Failed to generate singed certs for %s", CSR_NAME)
        exit(1)

    logger.info("Successfully completed generating Certs for %s", CSR_NAME)
    copyfile("/tmp/server-key.pem", path.join(ssl_path, "key.pem"))
    copyfile("/tmp/server-cert.pem", path.join(ssl_path, "cert.pem"))


if __name__ == "__main__":
    parser = ArgumentParser(description="Python Admission controller demo deployer")
    parser.add_argument(
        "--mode", "-m", choices=("deploy", "cleanup", "certs"), default="deploy"
    )
    args = parser.parse_args()
    if args.mode == "deploy":
        cleanup()
        deploy(_extract_ca_bundle())
    elif args.mode == "cleanup":
        cleanup()
    else:
        build_certs()

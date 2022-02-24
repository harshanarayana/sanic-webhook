import base64
import json as nativejson
import os
from copy import deepcopy

import jsonpatch
from sanic import Request, Sanic
from sanic.log import logger
from sanic.response import json

from kubernetes import config, client

import cowsay


config.load_incluster_config()

v1 = client.CoreV1Api()

app = Sanic(name=__name__)


@app.post("/audit")
async def audit(request: Request):
    logger.info(f"Obtained Request {request.json}")
    original_request = request.json
    return json(
        {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": {
                "uid": original_request["request"]["uid"],
                "allowed": True,
                "warnings": [
                    "this is really fun to do but equally annoying to see",
                ],
            },
        }
    )


@app.post("/deny-exec")
async def deny_exec(request: Request):
    original_request = request.json
    pod_name = original_request["request"]["name"]
    pod_namespace = original_request["request"]["namespace"]
    pods = v1.list_namespaced_pod(pod_namespace)
    for pod in pods.items:
        logger.info(f"Pricessing pod {pod.metadata.name} for exec options")
        oh_no = False
        if pod.metadata.name == pod_name:
            if pod.spec.host_pid:
                oh_no = True
            else:
                for container in pod.spec.containers:
                    if container.security_context and container.security_context.privileged:
                        oh_no = True
                        break
            if oh_no:
                return json(
                    {
                        "apiVersion": "admission.k8s.io/v1",
                        "kind": "AdmissionReview",
                        "response": {
                            "uid": original_request["request"]["uid"],
                            "allowed": False,
                            "status": {
                                "code": 403,
                                "message": "\n\n\n" + cowsay.get_output_string("tux", "You thought you could sneak in? Not on my watch!"),
                            },
                        },
                    }
                )
    return json(
        {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": {
                "uid": original_request["request"]["uid"],
                "allowed": True
            },
        }
    )


@app.post("/disallow-host-mounts")
async def disable_host_mounts(request: Request):
    original_request = request.json
    deployment = deepcopy(original_request["request"]["object"])
    volumes = (
        deployment.get("spec", {})
        .get("template", {})
        .get("spec", {})
        .get("volumes", [])
    )
    logger.info(
        f"Processing deployment {deployment.get('name')} for host mount volumes"
    )
    mounts = []
    new_volumes = []
    for vol in volumes:
        if vol.get("hostPath") is not None:
            mounts.append(vol["name"])
        else:
            new_volumes.append(vol)

    if len(volumes) != len(new_volumes):
        deployment["spec"]["template"]["spec"]["volumes"] = new_volumes

        for index in range(len(deployment["spec"]["template"]["spec"]["containers"])):
            volume_mounts = deployment["spec"]["template"]["spec"]["containers"][
                index
            ].get("volumeMounts")
            new_volume_mounts = []
            for vol in volume_mounts:
                if vol["name"] not in mounts:
                    new_volume_mounts = vol
            if len(volume_mounts) != len(new_volume_mounts):
                deployment["spec"]["template"]["spec"]["containers"][index][
                    "volumeMounts"
                ] = new_volume_mounts

    if mounts:
        annotations = deployment["metadata"].get("annotations", {})
        annotations["mks.cisco.com/mutated-for-host-path"] = "true"
        deployment["metadata"]["annotations"] = annotations

        patch = jsonpatch.make_patch(
            original_request["request"]["object"], deployment
        ).patch
        logger.info(f"JSONPatch {patch}")
        patch = base64.b64encode(nativejson.dumps(patch).encode()).decode()
        oh_no = f"Times have changed, allow we will not, hostMount in Pods. Found violation {','.join(mounts)}"
        return json(
            {
                "apiVersion": "admission.k8s.io/v1",
                "kind": "AdmissionReview",
                "response": {
                    "uid": original_request["request"]["uid"],
                    "allowed": True,
                    "warnings": [oh_no],
                    "patchType": "JSONPatch",
                    "patch": patch,
                },
            }
        )
    else:
        return json(
            {
                "apiVersion": "admission.k8s.io/v1",
                "kind": "AdmissionReview",
                "response": {
                    "uid": original_request["request"]["uid"],
                    "allowed": True,
                },
            }
        )


@app.post("/resource-enforce")
async def enforce_resource_requirements(request: Request):
    original_request = request.json
    pod = original_request["request"]["object"]
    containerMap = {"initContainers": [], "containers": []}
    containerMap["initContainers"] = pod["spec"].get("initContainers", [])
    containerMap["containers"] = pod["spec"]["containers"]
    error = False
    for key, containers in containerMap.items():
        logger.info(f"Processing {key} for resource enforcements")
        for container in containers:
            logger.info(
                f"Processing container {container['name']} for resource requirements"
            )
            if container.get("resources") is None:
                logger.error(
                    f"Container {container['name']} is missing resource information"
                )
                error = True

    if error:
        return json(
            {
                "apiVersion": "admission.k8s.io/v1",
                "kind": "AdmissionReview",
                "response": {
                    "uid": original_request["request"]["uid"],
                    "allowed": False,
                    "status": {
                        "code": 400,
                        "message": "I told you this was going to happen!",
                    },
                },
            }
        )
    else:
        return json(
            {
                "apiVersion": "admission.k8s.io/v1",
                "kind": "AdmissionReview",
                "response": {
                    "uid": original_request["request"]["uid"],
                    "allowed": True,
                },
            }
        )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=443)

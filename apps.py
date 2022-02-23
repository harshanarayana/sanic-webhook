import os
from sanic import Sanic, Request
from sanic.response import json
from sanic.log import logger
from copy import deepcopy

import json as nativejson
import jsonpatch
import base64

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
                ]
            }
        }
    )


@app.post("/disallow-host-mounts")
async def disable_host_mounts(request: Request):
    original_request = request.json
    deployment = deepcopy(original_request["request"]["object"])
    volumes = deployment.get("spec", {}).get("template", {}).get("spec", {}).get("volumes", [])
    logger.info(f"Processing deployment {deployment.get('name')} for host mount volumes")
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
            volume_mounts = deployment["spec"]["template"]["spec"]["containers"][index].get("volumeMounts")
            new_volume_mounts = []
            for vol in volume_mounts:
                if vol["name"] not in mounts:
                    new_volume_mounts = vol
            if len(volume_mounts) != len(new_volume_mounts):
                deployment["spec"]["template"]["spec"]["containers"][index]["volumeMounts"] = new_volume_mounts
    
    if mounts:
        annotations = deployment["metadata"].get("annotations", {})
        annotations["mks.cisco.com/mutated-for-host-path"] = "true"
        deployment["metadata"]["annotations"] = annotations

        patch = jsonpatch.make_patch(original_request["request"]["object"], deployment).patch
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
                    "patch": patch
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
                }
            }
        )


@app.post("/resource-enforce")
async def enforce_resource_requirements(request: Request):
    original_request = request.json
    pod = original_request["request"]["object"]
    containerMap = {
        "initContainers": [],
        "containers": []
    }
    containerMap["initContainers"] = pod["spec"].get("initContainers", [])
    containerMap["containers"] = pod["spec"]["containers"]
    error = False
    for key, containers in containerMap.items():
        logger.info(f"Processing {key} for resource enforcements")
        for container in containers:
            logger.info(f"Processing container {container['name']} for resource requirements")
            if container.get("resources") is None:
                logger.error(f"Container {container['name']} is missing resource information")
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
                        "message": "I told you this was going to happen!"
                    }
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
                }
            }
        )

ssl = {
    "cert": "/mnt/tls.crt",
    "key": "/mnt/tls.key",
}
if os.getenv("DEV_MODE"):
    app.run(host="0.0.0.0", port=443)
else:
    app.run(host="0.0.0.0", port=443, ssl=ssl)


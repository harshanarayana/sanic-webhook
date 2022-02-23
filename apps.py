import os
from sanic import Sanic, Request
from sanic.response import json
from sanic.log import logger

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
            if container.get("resource") is None:
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


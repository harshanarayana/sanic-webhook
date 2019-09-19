import asyncio
import base64
import json as json_loader
from copy import deepcopy

import jsonpatch
from loguru import logger
from sanic import Sanic
from sanic.request import Request
from sanic.response import json
from sanic_httpauth import HTTPBasicAuth

REGISTRIES_FILE = "/config/registries.json"
DO_NOT_DELETE = "maglev.cisco.com/do-not-delete"

app = Sanic(__name__)
auth = HTTPBasicAuth()


class AllowedRegistries:
    def __init__(self, registries):
        self._registries = registries

    def __contains__(self, registries):
        return registries in self._registries

    def update(self, registries):
        self._registries = registries


allowed_registries = AllowedRegistries(registries=[])


# noinspection PyBroadException
async def gather_allowed_registries():
    while True:
        try:
            # logger.info(f"Processing {REGISTRIES_FILE} for Allowed registries")
            with open(REGISTRIES_FILE) as fh:
                data = json_loader.load(fh)

            registries = data["allowed"]
            allowed_registries.update(registries=registries)
        except Exception:
            logger.exception(
                f"Failed to extract allowed registries from {REGISTRIES_FILE}"
            )
        await asyncio.sleep(5)


# noinspection PyBroadException
def is_base64(s):
    try:
        return base64.b64encode(base64.b64decode(s)) == s
    except Exception:
        return False


# noinspection PyBroadException
def _tackle_container_env(container):
    for index in range(len(container.get("env", []))):
        if (
            "secret" in container["env"][index]["name"].lower()
            or "srct" in container["env"][index]["name"].lower()
            or "password" in container["env"][index]["name"].lower()
            or "pwd" in container["env"][index]["name"].lower()
        ):
            if not is_base64(container["env"][index]["value"]):
                try:
                    container["env"][index]["value"] = base64.b64encode(
                        container["env"][index]["value"]
                    )
                except Exception:
                    logger.warning("Failed to B64 encode the contents of the ENV")


def parse_docker_image_name(image_name):
    folder = None
    registry = None
    tag = "latest"

    parts = image_name.rsplit("/", 3)
    part_count = len(parts)
    if part_count == 3:
        registry, folder, image_and_tag = parts
    elif part_count == 2:
        tmp, image_and_tag = parts
        if "." in tmp or ":" in tmp:
            registry = tmp
        else:
            folder = tmp
    else:
        image_and_tag = parts[0]

    parts = image_and_tag.rsplit(":", 2)
    if len(parts) == 2:
        image, tag = parts
    else:
        image = parts[0]

    return {"registry": registry, "folder": folder, "image": image, "tag": tag}


@auth.verify_password
def _verify_auth(username, password):
    if username == "harshanarayana" and password == "admin123":
        return True
    return False


# noinspection PyUnusedLocal
@app.post("/mutating")
async def mutating_webhook(request: Request):
    """
    This method is used to iterate over the container ENV used in the given
    request and check if there is any environment variable that has password
    or secret in it and if found, it will base64 encode the values used on
    that automatically.

    :param request:
    :return:
    """
    original_request = request.json
    modifiable_data = deepcopy(original_request)

    logger.info(f"Original Request: {original_request}")

    for container in modifiable_data["request"]["object"]["spec"]["template"]["spec"][
        "containers"
    ]:
        _tackle_container_env(container=container)

    patch = jsonpatch.JsonPatch.from_diff(
        original_request["request"]["object"], modifiable_data["request"]["object"]
    )

    logger.info(f"JSON Path: {patch}")

    if not patch:
        admission_response = {
            "allowed": True,
            "uid": original_request["request"]["uid"],
        }
    else:
        admission_response = {
            "allowed": True,
            "uid": original_request["request"]["uid"],
            "patch": base64.b64encode(str(patch).encode()).decode(),
            "patchtype": "JSONPatch",
        }

    admission_review = {"response": admission_response}

    logger.info(f"Admission Review: {admission_review}")
    return json(admission_review)


# noinspection PyProtectedMember
@app.post("/validating")
async def validating_webhook(request: Request):
    """
    This method is used to enforce that the image being used by the Resource
    that is coming up always uses an image from a known docker registry
    and nowhere else. (This can be combined with the AlwaysPull admission control to ensure that
    the images are pulled always and from the known source to ensure security)

    :param request:
    :return:
    """
    allowed = True
    original_request = request.json
    modifiable_data = deepcopy(original_request)
    error = {}
    if allowed_registries._registries:
        for container in modifiable_data["request"]["object"]["spec"]["template"][
            "spec"
        ]["containers"]:
            image_details = parse_docker_image_name(container["image"])

            if image_details["registry"] not in allowed_registries:
                registry = image_details["registry"]
                logger.error(f"{registry} is not in the list of allowed items")
                allowed = False
                error["code"] = 400
                error["message"] = (
                    f"Image used for container is not from an allowed registry. Allowed registries "
                    f"are: {allowed_registries._registries}"
                )
    else:
        logger.warning(
            f"Allowed registries webhook is enabled but the config map is missing the repo list. Allowing all"
        )
    return json(
        {
            "response": {
                "uid": original_request["request"]["uid"],
                "allowed": allowed,
                "status": error,
            }
        }
    )


@app.post("/validate-delete")
@auth.login_required
async def validate_deletes(request: Request):
    """
    This validating web-hook is triggered when a DELETE operation is invoked on a pod that is
    currently deployed.

    This method can easily be enhanced to include additional checks that can conditionally
    decide if a pod needs to be deleted or not.

    Currently, this method checks if the pod has a specific annotation that will indicate that
    deletion of this pod is not allowed, and if found, the request will be denied.

    :param request:
    :return:
    """
    allowed = True
    logger.info(f"Delete request: {request.json}")
    original_request = request.json
    error = {}
    logger.info(f"Checking if annotation for {DO_NOT_DELETE} is present.")
    annotations = (
        original_request["request"]
        .get("oldObject", {})
        .get("metadata", {})
        .get("annotations", {})
    )
    logger.info(f"Annotations for the Delete pod request: {annotations}")
    if annotations.get(DO_NOT_DELETE):
        logger.error(f"Found the disable delete annotation {DO_NOT_DELETE}")
        allowed = False
        error = {
            "core": 403,
            "message": f"You cannot delete a pod that has the annotation {DO_NOT_DELETE} attached to it",
        }
    response = json(
        {
            "response": {
                "uid": original_request["request"]["uid"],
                "allowed": allowed,
                "status": error,
            }
        }
    )
    logger.info(f"Response {response}")
    return response


if __name__ == "__main__":
    app.add_task(gather_allowed_registries())
    app.run(
        host="0.0.0.0",
        port=6543,
        debug=True,
        ssl={"cert": "/data/ssl/cert.pem", "key": "/data/ssl/key.pem"},
    )

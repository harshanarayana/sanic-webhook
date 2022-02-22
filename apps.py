import os
from sanic import Sanic, Request
from sanic.response import text, json
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
                "allowed": True
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


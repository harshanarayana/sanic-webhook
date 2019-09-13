from sanic import Sanic
from sanic.request import Request
from sanic.response import json
from sanic.log import logger

app = Sanic(__name__)


@app.post("/mutate")
async def webhook(request: Request):
    logger.info(request)
    logger.info(request.headers)
    logger.info(request.body)
    logger.info(request.json)
    return json(
        {
            "response": {
                "allowed": True,
            }
        }
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=6543,
        debug=True,
        ssl={
            "cert": "/data/ssl/cert.pem",
            "key": "/data/ssl/key.pem",
        }
    )

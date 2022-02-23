FROM sanicframework/sanic:3.8-latest

RUN pip install jsonpatch

COPY apps.py apps.py

ENTRYPOINT ["sanic", "apps.apps"]
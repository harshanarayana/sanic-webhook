FROM sanicframework/sanic:3.8-latest

RUN pip install jsonpatch
RUN pip install kubernetes
RUN pip install cowsay

COPY apps.py apps.py

ENTRYPOINT ["sanic", "apps.apps"]
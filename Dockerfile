FROM sanicframework/sanic:3.8-latest

RUN pip install jsonpatch
RUN pip install kubernetes
RUN pip install cowsay

COPY apps.py apps.py
COPY init.sh /init.sh
RUN chmod 755 /init.sh
COPY admission/validating.yaml /validating.yaml
COPY admission/mutating.yaml /mutating.yaml

ENTRYPOINT ["sanic", "apps:app", "--host=0.0.0.0", "--port=443", "--fast", "--cert=/mnt/tls.crt", "--key=/mnt/tls.key"]

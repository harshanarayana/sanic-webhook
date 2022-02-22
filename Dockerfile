FROM sanicframework/sanic:3.8-latest

COPY apps.py apps.py

ENTRYPOINT ["sanic", "apps.apps"]
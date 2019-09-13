FROM python:3.7.4-stretch

RUN pip install sanic
COPY app.py /app.py

RUN mkdir -p /data

COPY ssl/*.pem /data/ssl/

ENTRYPOINT ["python", "app.py"]
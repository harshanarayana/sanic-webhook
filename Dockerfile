FROM harshanarayana/sanic:v1

# Setup Directory structures
RUN mkdir -p /data
RUN mkdir -p /config

# Copy host files
COPY ssl/*.pem /data/ssl/
COPY app.py /app.py

# Configure Entry point
ENTRYPOINT ["python", "app.py"]

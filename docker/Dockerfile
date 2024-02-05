FROM python:3.9.15-slim-buster

WORKDIR /sentiment_analyzer
COPY . /sentiment_analyzer

RUN apt-get update && \
    apt-get install -y gcc libpq-dev && \
    pip install -r requirements.txt

EXPOSE 5001

CMD ["gunicorn", "-c", "docker/gunicorn_conf.py", "app:app"]
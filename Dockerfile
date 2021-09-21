FROM python:3.9-alpine3.13

RUN apk add bash

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONFAULTHANDLER=1
ENV PATH $PATH:/home/python/.local/bin

RUN adduser --disabled-password --uid 1000 python

USER python

RUN mkdir /home/python/app

WORKDIR /home/python/app

COPY requirements.txt .

RUN pip install -r requirements.txt
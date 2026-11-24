ARG BASE_IMAGE=python:3.12-slim
FROM ${BASE_IMAGE}
RUN useradd --uid 1000 --create-home --shell /bin/sh agent
USER agent
WORKDIR /workspace

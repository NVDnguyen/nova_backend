# syntax=docker/dockerfile:1
# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set environment variables to prevent generating .pyc files and to run in unbuffered mode
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY backend/requirements.txt .

# Install any needed packages specified in requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt

# Copy the backend application code into the container
COPY ./backend /app/backend

# The command to run the application will be specified in docker-compose.yml
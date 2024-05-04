# Use an appropriate base image (e.g., Ubuntu)
FROM nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04
ARG DEBIAN_FRONTEND=noninteractive

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY ./app /app

# Install ffmpeg and python requirements
RUN apt-get update \
    && apt-get install --no-install-recommends -y ffmpeg python3 python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt \
    && mkdir -p /models/drumsep \
    && cd /models/drumsep \
    && gdown 1VDMusvUmPuFKuJdkNfV4FWbiC6UJ25l8

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Define environment variable
ENV NVIDIA_VISIBLE_DEVICES all
ENV NVIDIA_DRIVER_CAPABILITIES compute,utility
ENV TF_ENABLE_ONEDNN_OPTS 0
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0

# Run app.py when the container launches
CMD ["flask", "run"]
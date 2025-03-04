FROM pytorch/pytorch:2.3.1-cuda11.8-cudnn8-devel

# Create the app directory
RUN mkdir /app
COPY . /app/

# Set working directory to /app
WORKDIR /app

# Update apt-get and install dependencies
RUN apt-get update && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variable for application home
ENV HOME=/app

# Start Redis and then your application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]


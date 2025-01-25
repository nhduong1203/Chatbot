# Use PyTorch base image
FROM pytorch/pytorch:2.3.1-cuda11.8-cudnn8-devel

# Create application directory and copy files
RUN mkdir /app
COPY . /app/

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Add a wait-for-it script to handle service dependencies
ADD https://raw.githubusercontent.com/vishnubob/wait-for-it/master/wait-for-it.sh /wait-for-it.sh
RUN chmod +x /wait-for-it.sh

# Set environment variable for application home
ENV HOME=/app

# Define the entrypoint to wait for Cassandra and start the application
ENTRYPOINT ["/wait-for-it.sh", "cassandra:9042", "-t", "180", "--"]

# Start the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]

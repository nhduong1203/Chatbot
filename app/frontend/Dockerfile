FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Copy only requirements.txt first to leverage caching properly
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the rest of the application code
COPY . /app/

# Expose the desired port
EXPOSE 8081

# Run the Streamlit application
CMD ["streamlit", "run", "QA.py", "--server.port", "8081"]

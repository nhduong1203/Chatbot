import os
from minio import Minio
import io
from opentelemetry import trace
from PyPDF2 import PdfReader
import logging

logging.basicConfig(
    level=logging.INFO,  
    format="%(asctime)s [%(levelname)s] %(message)s",  
    handlers=[
        logging.StreamHandler()  
    ]
)

logger = logging.getLogger(__name__)

class MinioManager:
    def __init__(self, minio_host=None, minio_port=None, minio_access_key=None, minio_secret_key=None, minio_secure=False):
        self.minio_host = minio_host or os.getenv("MINIO_HOST", "localhost")
        self.minio_port = minio_port or os.getenv("MINIO_PORT", "9000")
        self.minio_access_key = minio_access_key or os.getenv("MINIO_ACCESS_KEY", "admin")
        self.minio_secret_key = minio_secret_key or os.getenv("MINIO_SECRET_KEY", "admin123")
        self.minio_secure = minio_secure

        self.minio_client = Minio(
            f"{self.minio_host}:{self.minio_port}",
            access_key=self.minio_access_key,
            secret_key=self.minio_secret_key,
            secure=self.minio_secure
        )

    def ensure_bucket_exists(self, bucket_name: str):
        with trace.get_tracer(__name__).start_as_current_span("ensure_bucket_exists") as span:
            if not self.minio_client.bucket_exists(bucket_name):
                self.minio_client.make_bucket(bucket_name)


    async def upload_to_minio(self, bucket_name, user_id, chat_id, upload_option, url=None, uploaded_files=None):
        """
        Save data to MinIO.

        Args:
            bucket_name: Name of the MinIO bucket.
            user_id: ID of the user uploading the content.
            chat_id: ID of the chat associated with the upload.
            upload_option: Type of upload (e.g., "Upload Files" or "Website URL").
            url: URL to be processed, if applicable.
            uploaded_files: List of uploaded file objects, if applicable.
        """
        # Ensure the bucket exists
        if not self.minio_client.bucket_exists(bucket_name):
            self.minio_client.make_bucket(bucket_name)

        if upload_option == "Website URL" and url:
            # Handle URL uploads
            unique_id = hash(url)  # Generate a unique ID for the URL
            object_name = f"users/{user_id}/chats/{chat_id}/reference-documents/urls/{unique_id}.txt"
            try:
                url_content = url.encode("utf-8")
                data = io.BytesIO(url_content)
                self.minio_client.put_object(bucket_name, object_name, data, length=len(url_content))
                print(f"URL '{url}' saved successfully to MinIO.")
            except Exception as e:
                print(f"Failed to upload URL to MinIO: {e}")
                raise

        elif upload_option == "Upload Files" and uploaded_files:
            # Handle file uploads
            for uploaded_file in uploaded_files:
                try:
                    file_content = None
                    file_type = "txt" if uploaded_file.content_type == "text/plain" else "pdf"

                    # Extract content from PDF or text file
                    if file_type == "pdf":
                        with io.BytesIO(await uploaded_file.read()) as file_stream:
                            reader = PdfReader(file_stream)
                            file_content = "".join(page.extract_text() for page in reader.pages).encode("utf-8")
                    elif file_type == "txt":
                        file_content = await uploaded_file.read()

                    if not file_content:
                        raise ValueError(f"Unable to extract content from file: {uploaded_file.filename}")

                    # Upload the file content to MinIO
                    object_name = f"users/{user_id}/chats/{chat_id}/reference-documents/{uploaded_file.filename}"
                    data = io.BytesIO(file_content)
                    self.minio_client.put_object(bucket_name, object_name, data, length=data.getbuffer().nbytes)
                    print(f"File '{uploaded_file.filename}' uploaded successfully to MinIO.")
                except Exception as e:
                    print(f"Failed to upload file '{uploaded_file.filename}' to MinIO: {e}")
                    raise
        else:
            print("No valid upload option or data provided.")
            raise ValueError("Invalid upload option or no data to upload.")
        
    async def delete_from_minio(self, bucket_name, user_id, chat_id, file_name=None, upload_option=None):
        """
        Delete data from MinIO.

        Args:
            bucket_name: Name of the MinIO bucket.
            user_id: ID of the user associated with the file.
            chat_id: ID of the chat associated with the file.
            file_name: Name of the file to delete (for "Upload Files").
            upload_option: Type of upload (e.g., "Upload Files" or "Website URL").
        """
        try:
            # Construct the object name based on the upload option
            if upload_option == "Website URL":
                unique_id = hash(file_name)  # Generate a unique ID for the URL
                object_name = f"users/{user_id}/chats/{chat_id}/reference-documents/urls/{unique_id}.txt"
                logger.info(f"remove object name: {object_name}")
            elif upload_option == "Upload Files" and file_name:
                object_name = f"users/{user_id}/chats/{chat_id}/reference-documents/{file_name}"
                logger.info(f"remove object name: {object_name}")
            else:
                print("Invalid upload option or missing file name.")
                raise ValueError("Invalid upload option or missing file name.")

            # Check if the object exists
            if not self.minio_client.stat_object(bucket_name, object_name):
                print(f"Object '{object_name}' does not exist in bucket '{bucket_name}'.")
                raise FileNotFoundError(f"Object '{object_name}' not found.")

            # Delete the object from MinIO
            self.minio_client.remove_object(bucket_name, object_name)
            print(f"Object '{object_name}' deleted successfully from bucket '{bucket_name}'.")

        except Exception as e:
            print(f"Failed to delete object from MinIO: {e}")
            raise
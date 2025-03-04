from fastapi import FastAPI, UploadFile, Form, HTTPException
from typing import List, Optional
from PyPDF2 import PdfReader
from document import Embedder, SemanticChunker
from utils import crawl_website, convert_html_to_text
from database_manager import RedisVectorIndexManager, MinioManager
from pydantic import BaseModel

import os
import logging

from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import get_tracer_provider, set_tracer_provider

# Configure Jaeger tracing
set_tracer_provider(
    TracerProvider(resource=Resource.create({SERVICE_NAME: "file-upload-service"}))
)
tracer = get_tracer_provider().get_tracer("file_upload_tracer")
jaeger_exporter = JaegerExporter(
    agent_host_name="jaeger-agent.observability.svc.cluster.local",
    agent_port=6831,
)
span_processor = BatchSpanProcessor(jaeger_exporter)
get_tracer_provider().add_span_processor(span_processor)

# Initialize other components
embedder = Embedder()
chunker = SemanticChunker(embedder.model)
redis_manager = RedisVectorIndexManager()
minio_manager = MinioManager()

app = FastAPI()

# Configure logging
logging.basicConfig(
    level=logging.INFO,  
    format="%(asctime)s [%(levelname)s] %(message)s",  
    handlers=[
        logging.StreamHandler()  
    ]
)

logger = logging.getLogger(__name__)

@app.post("/upload")
async def handle_upload(
    user_id: str = Form(...),
    chat_id: str = Form(...),
    url: Optional[str] = Form(None),
    uploaded_files: Optional[List[UploadFile]] = None
):
    """Handle upload requests for URLs or files."""
    with tracer.start_as_current_span("handle_upload") as span:
        span.set_attribute("user_id", user_id)
        span.set_attribute("chat_id", chat_id)
        bucket_name = "my-bucket"
        minio_manager.ensure_bucket_exists(bucket_name)
        

        if url:
            with tracer.start_as_current_span("process_url") as url_span:
                url_span.set_attribute("url", url)
                await minio_manager.upload_to_minio(bucket_name, user_id, chat_id, "Website URL", url=url)
                crawl_result = crawl_website(url)
                if crawl_result['status'] == 'success':
                    plain_text = convert_html_to_text(crawl_result['content'])
                    chunks = chunker.process_file(plain_text)
                    chunks_and_embeddings = embedder.embed_chunks(chunks)
                    doc_id = f"{user_id}:{chat_id}:{hash(url)}"
                    redis_manager.store_chunks(doc_id, chunks_and_embeddings)
                    return {"status": "success", "message": "URL processed and stored successfully."}
                else:
                    url_span.record_exception(Exception(crawl_result['error']))
                    return {"status": "error", "message": crawl_result['error']}

        results = []

        if uploaded_files:
            await minio_manager.upload_to_minio(bucket_name, user_id, chat_id, "Upload Files", uploaded_files=uploaded_files)
            for uploaded_file in uploaded_files:
                uploaded_file.file.seek(0)

            for uploaded_file in uploaded_files:
                with tracer.start_as_current_span("process_file") as file_span:
                    file_span.set_attribute("filename", uploaded_file.filename)
                    try:
                        logger.info(uploaded_file.content_type)
                        if uploaded_file.content_type == "application/pdf":
                            file_span.set_attribute("content_type", "application/pdf")
                            try:
                                reader = PdfReader(uploaded_file.file)
                                file_content = ""
                                for i, page in enumerate(reader.pages):
                                    try:
                                        text = page.extract_text()
                                        if text:
                                            file_content += text
                                    except Exception as e:
                                        logger.error(f"Error extracting text from page {i + 1}: {e}")
                            except Exception as e:
                                file_span.record_exception(e)
                                results.append({"filename": uploaded_file.filename, "status": "error", "message": f"Failed to process PDF: {e}"})
                                continue
                        elif uploaded_file.content_type == "text/plain":
                            file_content = await uploaded_file.read()
                            if not file_content:  # Check if the file is empty
                                logger.warning("Uploaded file is empty")
                            else:
                                file_content = file_content.decode("utf-8", errors="replace")
                        
                        if file_content:
                            chunks = chunker.process_file(file_content)
                            chunks_and_embeddings = embedder.embed_chunks(chunks)
                            doc_id = f"{user_id}:{chat_id}:{hash(uploaded_file.filename)}"
                            redis_manager.store_chunks(doc_id, chunks_and_embeddings)
                            results.append({"filename": uploaded_file.filename, "status": "success", "message": "File processed and stored successfully."})
                        else:
                            results.append({"filename": uploaded_file.filename, "status": "error", "message": "Empty file content."})
                    except Exception as e:
                        file_span.record_exception(e)
                        results.append({"filename": uploaded_file.filename, "status": "error", "message": str(e)})

                

        if results:
            return {"status": "success", "results": results}
        else:
            span.record_exception(ValueError("No valid input provided."))
            return {"status": "error", "message": "No valid input provided."}
        
class RemoveDocumentRequest(BaseModel):
    user_id: str
    chat_id: str
    upload_option: str
    document_name: str

@app.post("/remove_document")
async def remove_document(request: RemoveDocumentRequest):
    """Remove a document from MinIO and Redis based on its name."""
    with tracer.start_as_current_span("remove_document") as span:
        span.set_attribute("document_name", request.document_name)
        span.set_attribute("upload_option", request.upload_option)
        span.set_attribute("user_id", request.user_id)
        span.set_attribute("chat_id", request.chat_id)

        try:
            bucket_name = "my-bucket"

            # Remove from MinIO
            with tracer.start_as_current_span("remove_from_minio") as minio_span:
                try:
                    await minio_manager.delete_from_minio(
                        bucket_name=bucket_name,
                        user_id=request.user_id,
                        chat_id=request.chat_id,
                        file_name=request.document_name,
                        upload_option=request.upload_option,
                    )
                    minio_span.set_attribute("minio_status", "success")
                except Exception as e:
                    minio_span.record_exception(e)
                    raise HTTPException(status_code=500, detail=f"Failed to remove document from MinIO: {e}")

            # Remove from Redis
            with tracer.start_as_current_span("remove_from_redis") as redis_span:
                doc_id = f"{request.user_id}:{request.chat_id}:{hash(request.document_name)}"
                redis_span.set_attribute("doc_id", doc_id)

                try:
                    redis_manager.delete_chunks(doc_id)
                    redis_span.set_attribute("redis_status", "success")
                except Exception as e:
                    redis_span.record_exception(e)
                    raise HTTPException(status_code=500, detail=f"Failed to remove document from Redis: {e}")

            return {"status": "success", "message": f"Document '{request.document_name}' removed successfully."}

        except Exception as e:
            span.record_exception(e)
            raise HTTPException(status_code=500, detail=str(e))




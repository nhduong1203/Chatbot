from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from llm_call import GenerateRAGAnswer
from database_manager import CassandraMessageStore
import asyncio
import os
import logging
import json

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor


# Configure OpenTelemetry Tracer
resource = Resource(attributes={SERVICE_NAME: "chat-service"})
provider = TracerProvider(resource=resource)
jaeger_exporter = JaegerExporter(
    agent_host_name="jaeger-agent.observability.svc.cluster.local",
    agent_port=6831,
)
provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Default log level
    format="%(asctime)s [%(levelname)s] %(message)s",  # Log format
    handlers=[
        logging.StreamHandler()  # Log to stdout (container best practice)
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI()
rag = GenerateRAGAnswer()

class UserState:
    """Maintains state for a single user."""
    def __init__(self):
        self.counter = 0  # Example state: a counter
        self.history_init = True
        self.cassandra = CassandraMessageStore()

    def retrieve_chat_history(self, conversation_id):
        chat_history = self.cassandra.get_chat_history(conversation_id=conversation_id)
        return chat_history

    def increment_counter(self):
        self.counter += 1
        return self.counter

@app.websocket("/ws/{conversation_id}")
async def websocket_message_response(websocket: WebSocket, conversation_id: str):
    user_state = UserState()
    await websocket.accept()
    
    try:
        while True:
            # Receive a message from the client (e.g., chat_id, message, timestamp)
            data = await asyncio.wait_for(websocket.receive_text(), timeout=300)
            # ---------------------------------------------------------------------
            # Assuming the message is a JSON string with fields chat_id, message, timestamp
            message_data = json.loads(data)
            user_id = message_data["user_id"]
            conversation_id = message_data["chat_id"]
            message = message_data["message"]

            
            with tracer.start_as_current_span("message") as span:
                span.set_attribute("user_id", user_id)
                span.set_attribute("conversation_id", conversation_id)
                span.set_attribute("message", message)

                try:
                    # Generate an LLM answer using RAG (or any other method)
                    if user_state.history_init == True:
                        user_state.history_init = False
                        chat_history = user_state.retrieve_chat_history(conversation_id=conversation_id)
                    if not chat_history: 
                        chat_history = ["There is currently no message history."]
                        
                    generator = rag.generate_llm_answer(query=message, user_id=user_id, conversation_id=conversation_id, chat_history=chat_history)
                    
                    logger.info(f"chat_history: {chat_history}")

                    # Stream responses to the WebSocket client
                    for answer in generator:
                        await websocket.send_text(answer)

                    await websocket.send_text("/end")

                except Exception as e:
                    span.record_exception(e)
                    logger.error(f"Error generating response: {e}")
                    await websocket.send_text("Error generating response")
                    break

    except WebSocketDisconnect:
        logger.info(f"Client {user_id} disconnected")

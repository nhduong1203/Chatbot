import torch
import os
from database_manager import RedisManager, CassandraMessageStore
from .endpoint_request import standalone_question, get_openai_stream_response
from datetime import datetime, timezone
from datetime import datetime
import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor


# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Default log level
    format="%(asctime)s [%(levelname)s] %(message)s",  # Log format
    handlers=[
        logging.StreamHandler()  # Log to stdout (container best practice)
    ]
)
logger = logging.getLogger(__name__)

# Configure OpenTelemetry Tracer
resource = Resource(attributes={SERVICE_NAME: "rag-system"})
provider = TracerProvider(resource=resource)
jaeger_exporter = JaegerExporter(
    agent_host_name="jaeger-agent.observability.svc.cluster.local",
    agent_port=6831,
)
provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


class GenerateRAGAnswer:
    def __init__(self):
        self.redis_manager = RedisManager()
        self.cassandra_manager = CassandraMessageStore()

    def generate_llm_answer(self, query, user_id="user123", conversation_id="chat456", chat_history=None):
        with tracer.start_as_current_span("generate_llm_answer") as span:
            span.set_attribute("query", query)
            query_time = datetime.now(timezone.utc)
            contexts = self.redis_manager.retrieve_contexts(query, user_id, conversation_id)

            if chat_history:
                chat_history_joined = "\n".join(chat_history)
            else: 
                chat_history_joined = ""
            standalone_final_query = standalone_question(query=query, chat_history=chat_history_joined)

            logger.info(f"standalone_final_query:\n {standalone_final_query}")

            final_response = ""
            for chunk in get_openai_stream_response(message=standalone_final_query, context=contexts):
                yield chunk
                final_response += chunk
            
            chat_history.append(f"user: {query}")
            chat_history.append(f"assistant: {final_response}")
            if len(chat_history) % 2 == 1:
                chat_history = chat_history[1:]
            if len(chat_history) > 4:
                chat_history = chat_history[2:]

            self.cassandra_manager.save_message(user_id=user_id, conversation_id=conversation_id, message=query, role="User", timestamp=query_time)
            self.cassandra_manager.save_message(user_id=user_id, conversation_id=conversation_id, message=final_response, role="Bot")


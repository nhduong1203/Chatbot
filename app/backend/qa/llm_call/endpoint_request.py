import os
import requests
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Configure OpenTelemetry Tracer
resource = Resource(attributes={SERVICE_NAME: "chat-service"})
provider = TracerProvider(resource=resource)
jaeger_exporter = JaegerExporter(
    agent_host_name=os.getenv("JAEGER_AGENT_HOST", "jaeger-agent.observability.svc.cluster.local"),
    agent_port=int(os.getenv("JAEGER_AGENT_PORT", 6831)),
)
provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)

# Get the model gateway IP
ASM_GATEWAY_IP = os.environ.get("ASM_GATEWAY_IP", "localhost")
MODEL_ENDPOINT = f"http://{ASM_GATEWAY_IP}:80/v2/models/ensemble/generate"


def get_custom_model_response(message, context=None, max_tokens=250):
    """
    Sends a request to the custom model API and retrieves the response.
    
    Parameters:
        message (str): The user's input message.
        context (str, optional): Additional context information.
        max_tokens (int): The maximum number of tokens to generate.

    Returns:
        str: The generated response from the model.
    """
    payload = {
        "text_input": message,
        "max_tokens": max_tokens,
        "bad_words": "",
        "stop_words": "",
        "pad_id": 2,
        "end_id": 2
    }
    headers = {
        "Host": "llama.default.example.com",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(MODEL_ENDPOINT, json=payload, headers=headers)
        response.raise_for_status()
        
        output = response.json().get("text_output", "")
        return output.strip()
    except Exception as e:
        raise Exception(f"An error occurred: {e}")


def standalone_question(query="", chat_history="", max_tokens=1000):
    """
    Create a SINGLE standalone question based on a new question and chat history.
    If the new question can stand on its own, return it directly.
    
    Parameters:
        query (str): The new question.
        chat_history (str): The chat history.
        max_tokens (int): The maximum number of tokens to generate.
    
    Returns:
        str: The standalone question.
    """
    prompt = f"""Create a SINGLE standalone question. The question should be based on the New question plus the Chat history. \
    If the New question can stand on its own you should return the New question. New question: \"{query}\", Chat history: \"{chat_history}\"."""
    
    return get_custom_model_response(prompt, max_tokens=max_tokens)


if __name__ == '__main__':
    print(standalone_question("What is a spotlist?"))
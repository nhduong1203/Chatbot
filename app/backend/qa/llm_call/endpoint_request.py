import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
import openai

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

api_key = os.environ.get("OPENAI_API_KEY")
model = "gpt-3.5-turbo"
openai.api_key = api_key

def get_openai_stream_response(message, context=None, max_tokens=250):
    """
    Sends a request to OpenAI's API and retrieves the response in streaming mode for chat models.

    Parameters:
        message (str): The user's input message.
        context (str, optional): Additional context information to provide to the assistant.
        max_tokens (int): The maximum number of tokens to generate (default is 150).

    Returns:
        Generator: Yields chunks of the response content in a streaming manner.
    """
    # Base system prompt
    messages = [
        {"role": "system", "content": "You are a helpful assistant."}
    ]

    # Include context if provided
    if context:
        messages.append({"role": "system", "content": f"Context: {context}"})

    # Add the user message
    messages.append({"role": "user", "content": message})

    try:
        # Sending request to OpenAI's API
        response = openai.ChatCompletion.create(
            model="gpt-4",  # Specify the model
            messages=messages,
            max_tokens=max_tokens,
            stream=True  # Enable streaming response
        )

        for chunk in response:
            if 'choices' in chunk:
                # Extract content from the stream response
                delta = chunk['choices'][0]['delta']
                if 'content' in delta:
                    yield delta['content']

    except Exception as e:
        raise Exception(f"An unexpected error occurred: {e}")


def standalone_question(query="", chat_history="", max_tokens=1000):
    """
    Create a SINGLE standalone question based on a new question and chat history.
    If the new question can stand on its own, return it directly.

    Parameters:
        query (str): The query string (default: "What is a spotlist?").
        q (str): The new question.
        chat_history (str): The chat history.
        max_tokens (int): The maximum number of tokens to generate (default: 1000).

    Returns:
        str: The standalone question or response text.
    """
    prompt = f"""Create a SINGLE standalone question. The question should be based on the New question plus the Chat history. \
    If the New question can stand on its own you should return the New question. New question: \"{query}\", Chat history: \"{chat_history}\"."""

    try:
        response = openai.ChatCompletion.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an assistant that reformulates questions."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens
        )

        output_text = response["choices"][0]["message"]["content"].strip()
        return output_text

    except Exception as e:
        raise Exception(f"An unexpected error occurred: {e}")

if __name__ == '__main__':
    standalone_question()

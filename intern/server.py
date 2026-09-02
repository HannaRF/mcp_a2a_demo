"""
Intern — the A2A server (section 3.3 of the lecture).

Exposes an Agent Card at /.well-known/agent-card.json and a JSON-RPC
endpoint that accepts tasks. Internally, on each task, it runs an LLM
agentic loop that calls the Database MCP server to search the product catalog.

Run:
    python server.py         # starts on http://127.0.0.1:9000
    (requires catalog_server/server.py already running on port 8100)
"""
import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from executor import InternExecutor

HOST = "127.0.0.1"
PORT = 9000


def build_agent_card() -> AgentCard:
    skill = AgentSkill(
        id="search-products",
        name="Product search",
        description="Finds products in the catalog, filtering by price and category",
        tags=["catalog", "shopping", "search"],
        examples=["find me products under 20 euros", "electronics under 15 euros"],
    )
    return AgentCard(
        name="Intern",
        description="Answers questions about the company product catalog",
        url=f"http://{HOST}:{PORT}/",
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )


def main():
    request_handler = DefaultRequestHandler(
        agent_executor=InternExecutor(),
        task_store=InMemoryTaskStore(),
    )
    app = A2AStarletteApplication(
        agent_card=build_agent_card(),
        http_handler=request_handler,
    )
    uvicorn.run(app.build(), host=HOST, port=PORT)


if __name__ == "__main__":
    main()

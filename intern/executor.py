"""
Intern's AgentExecutor: bridges the A2A protocol to an LLM-driven agent
that uses Database MCP tools to answer questions about the product catalog.

Execution flow:
  1. Discover available tools from the Database MCP server (list_tools)
  2. Send the user query + tool schemas to the LLM
  3. Execute any tool calls the LLM requests, via MCP
  4. Feed results back as tool messages
  5. Repeat until the LLM produces a final text answer (finish_reason == "stop")

Environment variables:
  GROQ_API_KEY    — Groq API key (required); get one free at console.groq.com
  GROQ_MODEL      — model to use (default: llama-3.3-70b-versatile)
  LOG_REASONING=1 — print each tool call chosen and the MCP result
  LOG_SCHEMA=1    — print the tool schemas discovered from the MCP server
"""
import json
import os

from openai import AsyncOpenAI
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState
from a2a.utils import new_task, new_text_artifact

from mcp_client import mcp_session

MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
LOG_REASONING = os.getenv("LOG_REASONING", "1").lower() in ("1", "true", "yes")
LOG_SCHEMA = os.getenv("LOG_SCHEMA", "").lower() in ("1", "true", "yes")

SYSTEM_PROMPT = (
    "You are a catalog agent. You have access to tools that query a product "
    "catalog database. Use them to answer the user's question. Be concise and "
    "format product listings clearly, including name, price, and category. "
    "All prices are in euros (€)."
)


def _mcp_tools_to_openai(mcp_tools) -> list[dict]:
    """Convert MCP tool definitions to the OpenAI API tool format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": t.inputSchema,
            },
        }
        for t in mcp_tools
    ]


def _print_schema(mcp_tools) -> None:
    """Print the tool schemas discovered from the MCP server."""
    print("\n=== MCP Tool Contract (discovered via list_tools) ===")
    for t in mcp_tools:
        print(f"\n  {t.name}")
        print(f"    {t.description}")
        props = t.inputSchema.get("properties", {})
        required = set(t.inputSchema.get("required", []))
        for param, schema in props.items():
            req = "required" if param in required else "optional"
            type_ = schema.get("type", "any")
            desc = schema.get("description", "")
            suffix = f" — {desc}" if desc else ""
            print(f"    • {param}: {type_} ({req}){suffix}")
    print("=====================================================\n")


def _print_tool_call(name: str, args: dict) -> None:
    args_str = ", ".join(f"{k}={json.dumps(v)}" for k, v in args.items())
    print(f"[Intern] LLM → {name}({args_str})")


def _print_tool_result(name: str, content: list) -> None:
    count = 0
    for c in content:
        if c.get("type") == "text":
            try:
                parsed = json.loads(c["text"])
                count += len(parsed) if isinstance(parsed, list) else 1
            except (json.JSONDecodeError, KeyError):
                count += 1
    print(f"[Intern] MCP  ← {name} returned {count} item(s)")


async def _run_agentic_loop(user_text: str) -> str:
    """Run an LLM tool-use loop until the model produces a final text answer.

    Opens a single MCP session for the entire loop so that tool discovery
    and all subsequent tool calls share one connection.
    """
    llm = AsyncOpenAI(
        api_key=os.getenv("GROQ_API_KEY"),
        base_url="https://api.groq.com/openai/v1",
    )

    async with mcp_session() as session:
        # Step 1: discover what tools the MCP server exposes
        tools_result = await session.list_tools()
        tools = _mcp_tools_to_openai(tools_result.tools)

        if LOG_SCHEMA:
            _print_schema(tools_result.tools)

        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ]

        while True:
            response = await llm.chat.completions.create(
                model=MODEL,
                max_tokens=900,
                tools=tools,
                messages=messages,
            )

            choice = response.choices[0]
            msg = choice.message

            # Keep the full assistant turn in history
            assistant_entry: dict = {"role": "assistant", "content": msg.content}
            if msg.tool_calls:
                assistant_entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]
            messages.append(assistant_entry)

            if choice.finish_reason == "stop":
                if LOG_REASONING:
                    print("[Intern] LLM → stop (final answer ready)")
                return msg.content or "(no response)"

            if choice.finish_reason == "tool_calls":
                # Step 3: execute every tool call the LLM requested
                for tc in msg.tool_calls:
                    name = tc.function.name
                    args = json.loads(tc.function.arguments)

                    if LOG_REASONING:
                        _print_tool_call(name, args)

                    mcp_result = await session.call_tool(name, args)
                    result_content = [
                        {"type": "text", "text": c.text}
                        for c in mcp_result.content
                        if hasattr(c, "text")
                    ]

                    if LOG_REASONING:
                        _print_tool_result(name, result_content)

                    # Step 4: feed results back so the LLM can continue reasoning
                    result_text = "\n".join(c["text"] for c in result_content)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_text,
                    })

                continue

            return f"Unexpected finish reason: {choice.finish_reason}"



class InternExecutor(AgentExecutor):
    """Executes the 'search-products' skill using an LLM agentic loop."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.start_work()                                    # A2A: task → working

        user_text = context.get_user_input()                          # A2A: extract user message
        answer = await _run_agentic_loop(user_text)                   # MCP + LLM loop 

        await updater.add_artifact(
            [new_text_artifact(name="search-results", text=answer).parts[0]],
            name="search-results",
        )                                                             # A2A: return result
        await updater.complete()                                      # A2A: task → completed

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.update_status(TaskState.canceled)

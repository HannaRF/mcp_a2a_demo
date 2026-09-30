"""
Salesperson — the A2A client / orchestrator (section 3.7 of the lecture).

Step 1 (Discovery): reads the Intern's Agent Card.
Step 2 (Task submission): sends a natural-language task to the Intern.
Step 3-5: waits for the task to complete and prints the returned Artifact.

Run (with catalog_server and intern already running):
    python client.py "find me products under 20 euros"
"""
import asyncio
import os
import sys
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import Message, Part, Role, TextPart

ANALYST_URL = "http://127.0.0.1:9000"
QUIET = os.getenv("QUIET", "").lower() in ("1", "true", "yes")


async def main(user_text: str) -> None:
    async with httpx.AsyncClient(timeout=30) as httpx_client:
        # --- Step 1: Discovery ---
        resolver = A2ACardResolver(httpx_client=httpx_client, base_url=ANALYST_URL)
        agent_card = await resolver.get_agent_card()
        if not QUIET:
            print(f"[Salesperson] Discovered '{agent_card.name}': {agent_card.description}")
            print(f"[Salesperson] Skills offered: {[s.id for s in agent_card.skills]}\n")

        # --- Step 2: Task submission ---
        client = ClientFactory(ClientConfig(httpx_client=httpx_client)).create(agent_card)

        message = Message(
            role=Role.user,
            message_id=str(uuid4()),
            parts=[Part(root=TextPart(text=user_text))],
        )

        if not QUIET:
            print(f"[Salesperson] Delegating task to Intern: \"{user_text}\"")
        final_text = None
        async for event in client.send_message(message):
            task = event[0] if isinstance(event, tuple) else event
            status = getattr(task, "status", None)
            if status and not QUIET:
                print(f"[Intern] task status -> {status.state.value}")
            artifacts = getattr(task, "artifacts", None) or []
            for artifact in artifacts:
                for part in artifact.parts:
                    if hasattr(part.root, "text"):
                        final_text = part.root.text

        print(final_text or "(no artifact returned)")


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) or "find me products under 20 euros"
    asyncio.run(main(query))

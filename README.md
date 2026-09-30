# MCP + A2A - Demo Project 

A working, end-to-end system that shows MCP and A2A together:

![Architecture diagram](assets/Gemini_Generated_Image_5j085p5j085p5j08.jpeg)

- **Catalog Server** (`catalog_server/`): exposes the product catalog (SQLite) as four MCP tools via Streamable HTTP.
- **Intern** (`intern/`): an A2A server that, when it receives a task, runs an LLM agentic loop that calls MCP tools to fulfill it.
- **Salesperson** (`salesperson/`): an A2A client that reads the Intern's Agent Card and delegates a natural-language task to it.

Tested with: `mcp==1.9.4`, `a2a-sdk==0.3.7`, `openai`, Python 3.12.
LLM backend: **Groq** (free tier). Default model: `qwen/qwen3.8-27b`.

## Quick Start

**Step 1 -- Get a free Groq API key** (no credit card required):
1. Go to [console.groq.com](https://console.groq.com) and create an account
2. Navigate to **API Keys** → **Create API Key**, and copy the key (starts with `gsk_`)

**Step 2 -- Install and configure:**
```bash
git clone <repo-url> && cd mcp_a2a_demo
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
echo 'GROQ_API_KEY=gsk_...' > .env
```

**Step 3 -- Run:**
```bash
./run_demo.sh "find me electronics under 20 euros"
```

The script seeds the database, starts all three components, streams live reasoning from the Intern, and shuts everything down on exit. Logs go to `logs/catalog.log` and `logs/intern.log`.

---

## Running manually (three terminals)

Useful if you want to watch each component's output independently.

```bash
# Terminal 1 - Catalog Server (port 8100)
cd catalog_server && python server.py

# Terminal 2 — Intern (port 9000)
cd intern && LOG_REASONING=1 python -u server.py

# Terminal 3 - Salesperson
cd salesperson && python client.py "find me electronics under 20 euros"
```

## Example queries

**Simple — single tool call:**
```bash
# query_products
./run_demo.sh "find me electronics under 20 euros"
./run_demo.sh "show me home products under 15 euros"
./run_demo.sh "what stationery do you have under 5 euros?"

# get_catalog_summary
./run_demo.sh "what product categories do you have?"
./run_demo.sh "give me a summary of the catalog"

# get_product
./run_demo.sh "tell me about the wireless mouse"
```

**Complex — multiple tool calls:**
```bash
# query_products → compare_products
./run_demo.sh "find all electronics under 15 euros, compare them side by side, and tell me which is the best value for money"

# get_catalog_summary → query_products × N
./run_demo.sh "I have 30 euros to set up a home office. What should I buy across all categories?"
./run_demo.sh "I need 3 different gifts for colleagues, total budget 20 euros, one per category. What do you recommend and why?"

# query_products × 3 (one per category)
./run_demo.sh "I want to buy one item from each category, all under 10 euros. List the options per category and suggest the best combo"

# full report
./run_demo.sh "give me a full catalog report: categories available, price ranges, total items, and list every product sorted by price"
```

**Semantic failures — for classroom discussion:**
```bash
# wrong category name → LLM may pass category="office supplies" instead of "stationery"
./run_demo.sh "show me office supplies under 5 euros"

# no price defined → LLM may invent max_price or skip tool call
./run_demo.sh "find me something cheap for my desk"

# ambiguous category → may return empty or wrong results
./run_demo.sh "any good deals on tech accessories?"

# hallucinated product → LLM may call get_product() with a made-up id
./run_demo.sh "tell me about the mechanical keyboard"

# unit mismatch → LLM may treat "bucks" as euros
./run_demo.sh "what electronics can I get for 20 bucks?"
```

## What you'll see

```
[Salesperson] Discovered 'Intern': Answers questions about the company product catalog
[Salesperson] Skills offered: ['search-products']       <- A2A: what Salesperson sees

[Salesperson] Delegating task to Intern: "find me electronics under 20 euros"
[Intern] task status -> working
[Intern] LLM → query_products(max_price=20, category="electronics")  <- MCP: internal
[Intern] MCP  ← query_products returned 3 item(s)
[Intern] LLM → stop (final answer ready)
[Intern] task status -> completed

Here are the electronics available under €20:

- USB-C Cable 1m — €6.50
- Phone Stand — €9.99
- Wireless Mouse — €14.99
```

The Salesperson never calls the database directly. It delegates via A2A to the Intern, which decides which MCP tools to call, runs them, and returns a final answer.

Output modes:
- `./run_demo.sh "..."` — full output with tool calls (default)
- `LOG_REASONING=0 ./run_demo.sh "..."` — hides tool calls, shows status updates
- `QUIET=1 ./run_demo.sh "..."` — prints only the final artifact

## MCP tools available

| Tool | Parameters | Description |
|------|-----------|-------------|
| `query_products` | `max_price`, `category?` | Search products at or below a price, optionally filtered by category |
| `get_product` | `product_id` | Look up a single product by id |
| `get_catalog_summary` | _(none)_ | Aggregate stats: categories, counts, price ranges |
| `compare_products` | `product_ids` | Side-by-side comparison of multiple products by id |

## Where each protocol lives in the code

**MCP layer:**
- `catalog_server/server.py` - defines the four MCP tools (`@mcp.tool()`) and starts the server. Provider side.
- `intern/mcp_client.py` - `mcp_session()` context manager that opens a connection to the Catalog Server. Consumer side.

**A2A layer:**
- `intern/server.py` - builds the Agent Card and starts the A2A server.
- `salesperson/client.py` - reads the Agent Card, submits a task, and streams the result.

**The agentic loop (where MCP and A2A meet):**
- `intern/executor.py` - discovers MCP tools via `list_tools`, sends schemas to the LLM, executes tool calls via MCP, feeds results back, repeats until the LLM stops.

## Optional logging flags

- **`LOG_REASONING=1`** _(default)_ — prints each tool call the LLM chooses and the MCP result.
- **`LOG_SCHEMA=1`** — prints the full tool schemas discovered from the MCP server at startup. Useful for demonstrating the "tool schema as contract" point: rename a parameter in `catalog_server/server.py` and the Intern adapts automatically, with no code change.
- **`QUIET=1`** — suppresses all framework output; prints only the final artifact.

## Troubleshooting

- `ConnectionRefusedError` from Salesperson: make sure the Catalog Server is running before the Intern. With `run_demo.sh` this is handled automatically.
- If you change a port, update it in all three components (`MCP_SERVER_URL` in `intern/mcp_client.py`, `INTERN_URL` in `salesperson/client.py`).
- `GROQ_API_KEY` must be set before starting the Intern. Easiest: create a `.env` file (see `.env.example`).
- `429 Rate limit exceeded`: Groq free tier limits output to 1000 tokens/min on `qwen/qwen3.8-27b`. Wait a minute and retry, or set `GROQ_MODEL` to a different model.

# WorldSmith V3: The Agentic Worldbuilding Engine

WorldSmith V3 is an autonomous, agentic system designed to generate high-fidelity TTRPG settings. It leverages a "Three-Surface" architecture to combine the power of LLMs with the structure of a graph database and the usability of a local-first frontend.

## 🏗️ Architecture

### 1. The Logic Surface (Python/LangGraph)
The core brain of the system. It uses a cyclic graph architecture to orchestrate multiple specialized agents:
- **Architect:** Analyzes the source material and plans the simulation nodes.
- **Dispatcher:** Manages the recursion depth and queue.
- **Outliner:** Generates structural blueprints for entities based on "Dynamic Density" rules.
- **Creator:** Writes the actual content using faction-specific personas.
- **Editor:** The "Critique Loop" that enforces quality, formatting, and consistency.
- **Scanner:** Reads existing files to discover new entities and expand the graph.

### 2. The Memory Surface (Supabase/PostgreSQL)
A persistent semantic memory layer.
- **Vector Search:** Uses `pgvector` (768 dimensions) to store and retrieve lore chunks.
- **Hybrid Search:** Combines keyword matching with semantic similarity.
- **Parent Document Retrieval:** Fetches full context to prevent hallucination.

### 3. The Frontend Surface (Obsidian.md)
The user interface and visualization layer.
- **Local-First:** All content is written to a local Vault as Markdown files.
- **Dataview:** Uses YAML frontmatter (`type`, `tier`, `status`) to build dynamic dashboards.
- **ITS Theme:** Supports rich UI elements like Infoboxes and Callouts.
- **Graph View:** Visualizes the connections between entities via `[[WikiLinks]]`.

## 🛡️ Operations & Safety

- **Guardrails:** Path traversal protection prevents the agent from writing outside the Vault.
- **Token Budget:** A "Circuit Breaker" enforces a daily token limit (default 1M) to control costs.
- **Obsidian Bridge:** A Watchdog agent that lints content for frontend compatibility and visually verifies rendering.

## 🚀 Getting Started

### Prerequisites
- Python 3.12+
- Supabase Project
- Google Gemini API Key

### Installation
1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure environment variables in `.env`:
   ```env
   GOOGLE_API_KEY=your_key
   SUPABASE_URL=your_url
   SUPABASE_KEY=your_key
   VAULT_ROOT=/path/to/obsidian/vault
   MAX_DAILY_TOKENS=1000000
   ```

### Usage
Run the simulation:
```bash
python src/main.py
```

## 🧪 Testing
Run the test suite:
```bash
pytest
```
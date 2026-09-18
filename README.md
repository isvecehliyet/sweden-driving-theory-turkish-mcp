# Sweden Driving Theory Turkish MCP

Read-only MCP server for [ehliyetsinavi.se](https://www.ehliyetsinavi.se/) and Turkish-language Swedish driving theory.

## Tools

- `search_theory`
- `get_theory_page`
- `get_membership_plans`
- `get_free_theory_test`

## Local run

```bash
pip install -r requirements.txt
python server.py
```

MCP endpoint: `http://localhost:8000/mcp`  
Health endpoint: `http://localhost:8000/health`

## Render

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
python server.py
```

Environment variable:

- `EHLIYETSINAVI_API_BASE=https://www.ehliyetsinavi.se/wp-json/eh-chatgpt/v1`
- Optional: `MCP_ALLOWED_HOSTS=your-service.onrender.com,your-service.onrender.com:*`

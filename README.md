# AgentAuth

**The open-source identity and session management SDK for AI Agents.**

AI Agents need to authenticate to websites and services. Currently, developers hardcode cookies (insecure, breaks often) or get blocked by 2FA/Captchas. AgentAuth solves this.

## The Problem
```python
# What developers do today (insecure, fragile)
cookies = {"li_at": "AQEDAT...hardcoded..."}
response = requests.get("https://linkedin.com/feed", cookies=cookies)
```

## The Solution
```python
# With AgentAuth (secure, managed, audited)
from agent_auth import Agent, AgentAuthClient

agent = Agent.load("sales-bot")
client = AgentAuthClient(agent)

session = client.get_session("linkedin.com")
response = requests.get("https://linkedin.com/feed", cookies=session)
```

## Features

- Encrypted Vault - Sessions stored with AES encryption
- Agent Identities - Cryptographic identity for each agent (Ed25519)
- Scoped Access - Agents can only access approved domains
- Audit Logging - Track which agent accessed what and when
- No Hardcoded Secrets - Sessions managed separately from code

## Installation
```bash
pip install agent-auth
```

## Quick Start

### 1. Initialize the vault
```bash
agent-auth init
```

### 2. Create an agent
```bash
agent-auth create-agent sales-bot --scopes linkedin.com,gmail.com
```

### 3. Add a session
```bash
agent-auth add linkedin.com
```

### 4. Use in your code
```python
from agent_auth import Agent, AgentAuthClient

agent = Agent.load("sales-bot")
client = AgentAuthClient(agent)
session = client.get_session("linkedin.com")

import requests
response = requests.get("https://linkedin.com/feed", cookies=session)
```

## LangChain Integration

AgentAuth provides seamless integration with LangChain agents through pre-built tools that handle authenticated requests automatically.

### Available Tools

1. **`authenticated_request`** - Makes authenticated HTTP requests using stored session cookies. Perfect for accessing sites that require login (LinkedIn, Gmail, etc.)
2. **`get_session_cookies`** - Retrieves session cookies for a domain. Use this when you need cookies to make your own custom requests.

### Example Usage

```python
from langchain_openai import ChatOpenAI
from langchain.agents import initialize_agent, AgentType
from agent_auth.langchain import get_agentauth_tools

# Get AgentAuth tools for your agent
tools = get_agentauth_tools(
    agent_name="sales-bot",
    vault_password="your-vault-password"
)

# Initialize the LLM
llm = ChatOpenAI(model="gpt-4", temperature=0)

# Create the agent with AgentAuth tools
agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True
)

# Run a query that requires authentication
response = agent.run("Get my LinkedIn notifications")
```

The agent will automatically use the `authenticated_request` tool to access LinkedIn with your stored session cookies, making authenticated API calls on your behalf.

## CLI Commands

| Command | Description |
|---------|-------------|
| `agent-auth init` | Initialize encrypted vault |
| `agent-auth add <domain>` | Add a session for a domain |
| `agent-auth list-sessions` | List all stored sessions |
| `agent-auth create-agent <name> --scopes <domains>` | Create agent identity |
| `agent-auth agents` | List all registered agents |

## Chrome Extension

Export cookies from any site with one click:

![AgentAuth Chrome Extension](docs/images/extension.png)

1. Install the extension from `browser-extension/` folder
2. Go to any site you're logged into
3. Click the extension → Export Session Cookies
4. Use `agent-auth add <domain>` and paste the cookies

## Why AgentAuth?

As AI Agents proliferate, Agent Identity becomes a massive security hole. AgentAuth fixes this by treating agents as first-class identities with scoped, auditable access.

## License

MIT
# How to Handle Authentication for AI Agents (Without Hardcoding Cookies)

If you're building AI agents that interact with websites, you've probably run into this problem: your agent needs to be logged in.

The common solution? Hardcode cookies in your code:
```python
# What everyone does (don't do this)
cookies = {"session_id": "abc123", "auth_token": "xyz789"}
response = requests.get("https://example.com/dashboard", cookies=cookies)
```

This works until it doesn't:
- Sessions expire and your agent breaks
- Cookies leak into git repos
- No way to track which agent accessed what
- One leaked cookie = compromised account

## The Real Problem: Agents Don't Have Identities

When a human logs into a website, they have an identity. They authenticate, get a session, and the site knows who they are.

AI agents? They're identity ghosts. They borrow your cookies, pretend to be you, and hope nothing breaks.

This is fine when you have one agent running locally. But what happens when you have:
- Multiple agents accessing different services
- Agents running in production
- A team where everyone has their own credentials

You need a real solution.

## What Good Agent Auth Looks Like

After dealing with this problem repeatedly, I built AgentAuth — an open-source SDK that handles this properly.

Here's how it works:

### 1. Export Cookies From Your Browser

Instead of manually copying cookies from dev tools, use a Chrome extension:

- Go to the site (logged in)
- Click the extension
- Click "Export Session Cookies"
- Done

### 2. Store Them Encrypted

Sessions are stored in an encrypted vault on your machine — not in your code, not in environment variables.
```bash
agent-auth init  # Set up the vault
agent-auth add github.com  # Paste the exported cookies
```

### 3. Give Each Agent an Identity

Every agent gets a cryptographic identity (Ed25519 keys) and scoped permissions:
```bash
agent-auth create-agent github-bot --scopes github.com
```

This agent can ONLY access gi.com. It can't touch your LinkedIn or Gmail sessions.

### 4. Retrieve Sessions Securely
```python
from agent_auth import Agent, AgentAuthClient

agent = Agent.load("github-bot")
client = AgentAuthClient(agent)
cookies = client.get_session("github.com")

# Now use the cookies
response = requests.get("https://github.com/notifications", cookies=cookies)
```

### 5. Everything is Logged

Every session access is logged. You know exactly which agent accessed which domain and when.

## Why This Matters

Right now, there are thousands of AI agents running with hardcoded cookies. As agents become more common, this becomes a massive security hole.

Think about it:
- Agents accessing company data
- Agents running automations on your behalf
- Agents with access to sensitive accounts

Do you really want all of that authenticated with copy-pasted cookies in a `.env` file?

## Try It

AgentAuth is open source:
```bash
pip install agent-auth
```

GitHub: https://github.com/jacobgadek/agent-auth

It takes 5 minutes to set up:
1. `agent-auth init`
2. Export cookies with the Chrome extension
3. `agent-auth add <domain>`
4. Use `AgentAuthClient` in your code

If you're building agents, give it a try. I'd love feedback.

---

*Building something with AI agents? I'm working on making agent authentication a solved problem. Follow along on [Twitter](https://twitter.com/jlgadek) or check out the [GitHub repo](https://github.com/jacobgadek/agent-auth).*

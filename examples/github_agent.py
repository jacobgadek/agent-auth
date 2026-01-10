"""
GitHub Agent Demo using AgentAuth

This agent uses your stored GitHub session to fetch your notifications.
No hardcoded cookies required.

Usage:
    PYTHONPATH=. python examples/github_agent.py
"""

import requests
from agent_auth.identity import Agent
from agent_auth.vault import Vault


def main():
    print()
    print("=" * 50)
    print("  GitHub Agent Demo - Powered by AgentAuth")
    print("=" * 50)
    print()
    
    # Load agent
    print("[1/3] Loading agent identity...")
    try:
        agent = Agent.load("github-agent")
        print("      Agent: github-agent")
        print("      Scopes: {}".format(agent.identity.scopes))
    except FileNotFoundError:
        print("      Agent 'github-agent' not found.")
        print()
        print("Setup required:")
        print("  1. agent-auth create-agent github-agent --scopes github.com")
        print("  2. Go to github.com (logged in)")
        print("  3. Click AgentAuth extension -> Export -> Copy")
        print("  4. agent-auth add github.com (paste cookies)")
        return
    
    # Connect to vault
    print()
    print("[2/3] Connecting to vault...")
    vault_password = input("      Vault password: ")
    
    try:
        vault = Vault()
        vault.unlock(vault_password)
        print("      Vault unlocked")
    except Exception as e:
        print("      Error: {}".format(e))
        return
    
    # Test GitHub access
    print()
    print("[3/3] Accessing GitHub with stored session...")
    
    try:
        # Get session from vault
        print()
        print("      Fetching stored session...")
        session = vault.get_session("github.com")
        
        # Extract cookies from session object
        if hasattr(session, 'cookies'):
            cookies = session.cookies
        else:
            cookies = session
        
        print("      Session retrieved!")
        
        # Fetch notifications
        print("      Fetching GitHub notifications...")
        response = requests.get(
            "https://github.com/notifications",
            cookies=cookies,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            },
            allow_redirects=False
        )
        
        if response.status_code == 200:
            print("      Notifications loaded ({:,} bytes)".format(len(response.text)))
        elif "login" in response.headers.get("Location", "").lower():
            print("      Session expired - redirected to login")
            print("      Re-export cookies and run: agent-auth add github.com")
            return
        else:
            print("      Status: {}".format(response.status_code))
        
        # Fetch stars
        print("      Fetching starred repos...")
        response = requests.get(
            "https://github.com/stars",
            cookies=cookies,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            },
            allow_redirects=False
        )
        
        if response.status_code == 200:
            print("      Stars page loaded ({:,} bytes)".format(len(response.text)))
        
    except Exception as e:
        print("      Error: {}".format(e))
        import traceback
        traceback.print_exc()
        return
    
    print()
    print("=" * 50)
    print("  Demo complete!")
    print()
    print("  Your agent accessed GitHub securely using")
    print("  stored session cookies. No hardcoded secrets.")
    print("=" * 50)
    print()


if __name__ == "__main__":
    main()

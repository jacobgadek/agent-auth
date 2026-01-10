"""
Playwright + AgentAuth Example

This shows how to use AgentAuth to inject your authenticated session
into a Playwright browser - no manual login required.

Usage:
    PYTHONPATH=. python examples/browser-use/github_browser_agent.py
"""

import asyncio
import getpass
from playwright.async_api import async_playwright
from agent_auth.vault import Vault


def get_cookies_for_playwright(vault: Vault, domain: str) -> list:
    """
    Convert AgentAuth session cookies to Playwright format.
    """
    session = vault.get_session(domain)
    
    if hasattr(session, 'cookies'):
        raw_cookies = session.cookies
    else:
        raw_cookies = session
    
    playwright_cookies = []
    for name, value in raw_cookies.items():
        clean_value = str(value)
        if clean_value.startswith('"') and clean_value.endswith('"'):
            clean_value = clean_value[1:-1]
        if clean_value.startswith('\\"') and clean_value.endswith('\\"'):
            clean_value = clean_value[2:-2]
        
        cookie = {
            "name": str(name),
            "value": clean_value,
            "domain": ".github.com",
            "path": "/",
        }
        playwright_cookies.append(cookie)
    
    return playwright_cookies


async def main():
    print()
    print("=" * 55)
    print("  Playwright + AgentAuth Demo")
    print("=" * 55)
    print()
    
    print("[1/4] Connecting to vault...")
    vault_password = getpass.getpass("      Vault password: ")
    
    try:
        vault = Vault()
        vault.unlock(vault_password)
        print("      Vault unlocked!")
    except Exception as e:
        print(f"      Error: {e}")
        return
    
    print()
    print("[2/4] Loading GitHub session...")
    try:
        cookies = get_cookies_for_playwright(vault, "github.com")
        print(f"      Loaded {len(cookies)} cookies")
    except Exception as e:
        print(f"      Error: {e}")
        print("      Run: agent-auth add github.com")
        return
    
    print()
    print("[3/4] Launching browser with authenticated session...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        
        success_count = 0
        for cookie in cookies:
            try:
                await context.add_cookies([cookie])
                success_count += 1
            except Exception:
                pass
        
        print(f"      Injected {success_count}/{len(cookies)} cookies")
        
        page = await context.new_page()
        
        print()
        print("[4/4] Navigating to GitHub notifications...")
        await page.goto("https://github.com/notifications")
        
        await asyncio.sleep(3)
        
        title = await page.title()
        if "Sign in" in title:
            print("      Session expired or cookies invalid")
        else:
            print(f"      Success! Page title: {title}")
        
        print()
        print("      Browser will close in 5 seconds...")
        await asyncio.sleep(5)
        
        await browser.close()
    
    print()
    print("=" * 55)
    print("  Demo complete!")
    print("  Your browser used stored cookies from AgentAuth.")
    print("  No hardcoded credentials. No manual login.")
    print("=" * 55)
    print()


if __name__ == "__main__":
    asyncio.run(main())

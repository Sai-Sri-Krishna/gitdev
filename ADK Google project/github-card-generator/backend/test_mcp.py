import asyncio
import os
import json
from mcp_server import scrape_github, analyze_profile, generate_card_html, save_card
from dotenv import load_dotenv

load_dotenv()

async def test_workflow():
    username = "torvalds"
    print(f"--- 1. Testing scrape_github for {username} ---")
    try:
        github_data = await scrape_github(username)
        if "error" in github_data:
            print(f"FAILED: {github_data['error']}")
            return
        print("SUCCESS: Data fetched.")
    except Exception as e:
        print(f"FAILED: scrape_github threw exception: {e}")
        return

    print(f"\n--- 2. Testing analyze_profile ---")
    try:
        analysis = await analyze_profile(github_data)
        print("SUCCESS: Profile analyzed.")
        print(f"Vibe: {analysis.get('developer_vibe')}")
        print(f"Theme: {analysis.get('card_theme')}")
    except Exception as e:
        print(f"FAILED: analyze_profile threw exception: {e}")
        return

    print(f"\n--- 3. Testing generate_card_html ---")
    try:
        card_html = await generate_card_html(username, github_data, analysis)
        print("SUCCESS: HTML generated.")
    except Exception as e:
        print(f"FAILED: generate_card_html threw exception: {e}")
        return

    print(f"\n--- 4. Final Summary ---")
    print(f"Developer Vibe: {analysis.get('developer_vibe')}")
    print(f"Card Theme: {analysis.get('card_theme')}")

if __name__ == "__main__":
    asyncio.run(test_workflow())

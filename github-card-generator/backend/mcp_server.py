import os
import httpx
import json
from mcp.server.fastmcp import FastMCP
from google import genai
from google.genai import types
from dotenv import load_dotenv
from collections import Counter

load_dotenv()

mcp = FastMCP("GithubDevCard")
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

@mcp.tool()
async def scrape_github(username: str) -> dict:
    """Fetch comprehensive GitHub stats for a given username."""
    headers = {"User-Agent": "Github-Card-Generator"}
    if token := os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"token {token}"

    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as http_client:
        # Fetch user profile
        user_res = await http_client.get(f"https://api.github.com/users/{username}")
        if user_res.status_code != 200:
            return {"error": f"User not found: {user_res.status_code}"}
        user_data = user_res.json()

        # Fetch repos
        repos_res = await http_client.get(f"https://api.github.com/users/{username}/repos?sort=updated&per_page=100")
        repos_data = repos_res.json() if repos_res.status_code == 200 else []

        # Process top 6 repos by stars
        sorted_repos = sorted(repos_data, key=lambda x: x.get("stargazers_count", 0), reverse=True)[:6]
        top_repos = [
            {
                "name": r["name"],
                "stars": r["stargazers_count"],
                "language": r["language"],
                "description": r["description"]
            } for r in sorted_repos
        ]

        # Aggregate languages
        languages = [r["language"] for r in repos_data if r.get("language")]
        lang_counts = dict(Counter(languages).most_common(5))

        return {
            "name": user_data.get("name") or username,
            "bio": user_data.get("bio"),
            "location": user_data.get("location"),
            "public_repos": user_data.get("public_repos"),
            "followers": user_data.get("followers"),
            "avatar_url": user_data.get("avatar_url"),
            "top_repos": top_repos,
            "languages": lang_counts
        }

@mcp.tool()
async def analyze_profile(github_data: dict) -> dict:
    """Analyze GitHub data using Gemini to determine developer vibe and skills."""
    prompt = f"""
    Analyze this GitHub profile data and return a JSON object with:
    - developer_vibe: A 1-sentence personality summary.
    - top_skills: A list of 3 key technical skills.
    - fun_fact: A clever observation based on their repos.
    - card_theme: Choose exactly one: "hacker", "builder", "researcher", "designer", "open-source-hero".

    Data: {json.dumps(github_data)}
    """
    
    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    return json.loads(response.text)

@mcp.tool()
async def generate_card_html(username: str, github_data: dict, analysis: dict) -> str:
    """Generate a self-contained, themed HTML card for the developer."""
    theme = analysis.get("card_theme", "builder")
    
    # Simple theme mapping
    themes = {
        "hacker": "bg-gray-900 text-green-400 border-green-500",
        "builder": "bg-blue-900 text-white border-blue-400",
        "researcher": "bg-slate-800 text-slate-100 border-indigo-400",
        "designer": "bg-pink-50 text-gray-900 border-pink-300",
        "open-source-hero": "bg-orange-600 text-white border-white"
    }
    theme_class = themes.get(theme, themes["builder"])

    repos_html = "".join([
        f'<div class="mb-2 p-2 bg-black/20 rounded"><strong>{r["name"]}</strong> ⭐{r["stars"]} <span class="text-xs">({r["language"]})</span></div>'
        for r in github_data.get("top_repos", [])[:3]
    ])

    skills_html = "".join([
        f'<span class="px-2 py-1 bg-white/20 rounded-full text-xs mr-1">{skill}</span>'
        for skill in analysis.get("top_skills", [])[:2]
    ])

    html = f"""
    <div class="max-w-sm rounded-2xl overflow-hidden shadow-xl border-2 {theme_class} p-6 font-sans">
        <div class="flex items-center mb-4">
            <img class="w-16 h-16 rounded-full border-2 border-current mr-4" src="{github_data.get('avatar_url')}" alt="{username}">
            <div>
                <h2 class="text-xl font-bold">{github_data.get('name')}</h2>
                <p class="text-sm opacity-80">@{username}</p>
            </div>
        </div>
        <p class="italic mb-4">"{analysis.get('developer_vibe')}"</p>
        <div class="mb-4">{skills_html}</div>
        <div class="grid grid-cols-2 gap-4 mb-4 text-center">
            <div class="bg-black/10 p-2 rounded">
                <div class="text-lg font-bold">{github_data.get('public_repos')}</div>
                <div class="text-xs uppercase">Repos</div>
            </div>
            <div class="bg-black/10 p-2 rounded">
                <div class="text-lg font-bold">{github_data.get('followers')}</div>
                <div class="text-xs uppercase">Followers</div>
            </div>
        </div>
        <h3 class="font-bold mb-2 border-b border-current/30 pb-1 text-sm uppercase">Top Projects</h3>
        {repos_html}
        <p class="mt-4 text-[10px] opacity-60 text-center uppercase tracking-widest">{theme} mode activated</p>
    </div>
    """
    return html

@mcp.tool()
async def save_card(username: str, html: str) -> str:
    """Save the generated HTML card to a file."""
    os.makedirs("static/cards", exist_ok=True)
    file_path = f"static/cards/{username}.html"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html)
    return f"/static/cards/{username}.html"

if __name__ == "__main__":
    mcp.run()

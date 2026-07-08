import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService
from google.genai import types

# Import the agent and toolset from our agent module
from agent import github_card_agent

app = FastAPI(title="GitHub Dev Card Generator API")

# 1. Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Setup Services and Runner
# Note: In a production app, you might want to share the session service
runner = InMemoryRunner(
    agent=github_card_agent,
    app_name="github_card_app"
)
runner.auto_create_session = True
session_service = runner.session_service

# 3. Static Files Setup
static_dir = os.path.join(os.path.dirname(__file__), "static")
cards_dir = os.path.join(static_dir, "cards")
os.makedirs(cards_dir, exist_ok=True)

# Mount the static directory to serve saved cards
app.mount("/static", StaticFiles(directory=static_dir), name="static")

class GenerateRequest(BaseModel):
    username: str

@app.get("/health")
async def health():
    """Cloud Run health check endpoint."""
    return {"status": "healthy"}

@app.get("/card/{username}")
async def get_card(username: str):
    """Serve a specific card or return 404."""
    file_path = os.path.join(cards_dir, f"{username}.html")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Card not found")
    
    with open(file_path, "r", encoding="utf-8") as f:
        return {"username": username, "html": f.read()}

from mcp_server import scrape_github, analyze_profile, generate_card_html, save_card

async def static_analyze_profile(github_data: dict) -> dict:
    """A zero-AI analyzer that uses simple logic if Gemini is exhausted."""
    languages = list(github_data.get("languages", {}).keys())
    repos = github_data.get("public_repos", 0)
    
    # Simple rule-based vibe
    vibe = f"A prolific developer with {repos} projects, specializing in {', '.join(languages[:2])}."
    
    # Simple rule-based theme
    if "Python" in languages or "TypeScript" in languages:
        theme = "builder"
    elif "C" in languages or "C++" in languages:
        theme = "hacker"
    else:
        theme = "open-source-hero"
        
    return {
        "developer_vibe": vibe,
        "top_skills": languages[:2] if languages else ["Coding", "Git"],
        "fun_fact": f"Has contributed to {repos} public repositories!",
        "card_theme": theme
    }

@app.post("/generate")
async def generate_card(request: GenerateRequest):
    """
    Endpoint to trigger the agent to generate a card.
    Falls back to direct tool calls, then to static analysis if AI fails.
    """
    username = request.username
    user_id = "web_user"
    import uuid
    session_id = f"session_{username}_{uuid.uuid4().hex[:8]}"

    # --- TIER 1: Full Agent ---
    try:
        print(f"--- [TIER 1] Attempting Agent for {username} ---")
        agent_response_text = ""
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part(text=f"Generate a card for {username}")])
        ):
            if hasattr(event, 'text') and event.text:
                agent_response_text += event.text
            elif hasattr(event, 'content') and event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        agent_response_text += part.text
        
        return {
            "username": username, "agent_narration": agent_response_text,
            "card_url": f"/static/cards/{username}.html"
        }

    except Exception as agent_err:
        print(f"Agent failed: {agent_err}. Trying [TIER 2] Direct AI Tools.")
        
        # --- TIER 2: Direct AI Tool Call ---
        try:
            github_data = await scrape_github(username)
            if "error" in github_data: raise HTTPException(status_code=404, detail=github_data["error"])
            
            analysis = await analyze_profile(github_data)
            card_html = await generate_card_html(username, github_data, analysis)
            card_url = await save_card(username, card_html)
            
            return {
                "username": username,
                "agent_narration": f"Generated via direct tool fallback. (Vibe: {analysis.get('developer_vibe')})",
                "card_url": card_url
            }
        except Exception as ai_err:
            print(f"AI Tools failed: {ai_err}. Trying [TIER 3] Zero-AI Fallback.")
            
            # --- TIER 3: Static Logic (Zero AI) ---
            try:
                github_data = await scrape_github(username)
                if "error" in github_data: raise HTTPException(status_code=404, detail=github_data["error"])
                
                analysis = await static_analyze_profile(github_data)
                card_html = await generate_card_html(username, github_data, analysis)
                card_url = await save_card(username, card_html)
                
                return {
                    "username": username,
                    "agent_narration": f"AI Quota Reached! Generated using local rules. (Vibe: {analysis.get('developer_vibe')})",
                    "card_url": card_url
                }
            except Exception as final_err:
                raise HTTPException(status_code=500, detail="Total failure across all tiers.")

@app.get("/")
async def read_index():
    """Serve the static frontend index.html."""
    return FileResponse(os.path.join(os.path.dirname(__file__), "../frontend/index.html"))

@app.get("/api/generate-card")
async def api_generate_card(username: str):
    """
    GET endpoint matching the Vercel serverless function signature.
    Generates the card and returns the HTML + narration directly.
    """
    try:
        # Call generate_card internally
        res = await generate_card(GenerateRequest(username=username))
        
        # Read the file
        file_path = os.path.join(cards_dir, f"{username}.html")
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                card_html = f.read()
        else:
            card_html = "<p>Error: Card file could not be generated.</p>"
        
        return {
            "username": username,
            "agent_narration": res.get("agent_narration"),
            "html": card_html
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)

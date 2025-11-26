# ======================================================
# 💼 DAY 5: AI SALES DEVELOPMENT REP (SDR)
# 🚀 Features: FAQ Retrieval, Lead Qualification, JSON Database
# ======================================================

import logging
import json
import os
import asyncio
from datetime import datetime
from typing import Annotated, Literal, Optional, List
from dataclasses import dataclass, asdict

print("\n" + "💼" * 50)
print("🚀 AI SDR AGENT - DAY 5 TUTORIAL")
print("📚 SELLING:  Zoho products")
print("� agent.py LOADED SUCCESSFULLY!")
print("💼" * 50 + "\n")

from dotenv import load_dotenv
from pydantic import Field
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    WorkerOptions,
    cli,
    function_tool,
    RunContext,
)

# 🔌 PLUGINS
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
load_dotenv(".env.local")

# ======================================================
# 📂 1. KNOWLEDGE BASE (FAQ)
# ======================================================

FAQ_FILE = "store_faq.json"
LEADS_FILE = "leads_db.json"

# Default FAQ data for "Kourses ai Store"
DEFAULT_FAQ =  [
    {
        "question": "What do you sell?",
        "answer": "We sell a comprehensive suite of business software called Zoho One. It includes over 50 applications for sales, marketing, support, accounting, and more, all integrated into one system."
    },
    {
        "question": "How much does Zoho One cost?",
        "answer": "Zoho One has two pricing plans: Flexible User Pricing at ₹2,100 per user per month, and All Employee Pricing at ₹900 per employee per month. I can have a specialist email you the full details."
    },
    {
        "question": "What is Zoho CRM?",
        "answer": "Zoho CRM is our customer relationship management software. It helps businesses manage sales, marketing, and customer support activities. It's also part of the Zoho One suite."
    },
    {
        "question": "Do you offer implementation support or training?",
        "answer": "Yes, absolutely. We have a network of certified partners who can help with implementation, and we offer extensive documentation, webinars, and paid training courses to help your team get started."
    }
]

def load_knowledge_base():
    """Generates FAQ file if missing, then loads it."""
    try:
        path = os.path.join(os.path.dirname(__file__), FAQ_FILE)
        if not os.path.exists(path):
            with open(path, "w", encoding='utf-8') as f:
                json.dump(DEFAULT_FAQ, f, indent=4)
        with open(path, "r", encoding='utf-8') as f:
            return json.dumps(json.load(f)) # Return as string for the Prompt
    except Exception as e:
        print(f"⚠️ Error loading FAQ: {e}")
        return ""

STORE_FAQ_TEXT = load_knowledge_base()

# ======================================================
# 💾 2. LEAD DATA STRUCTURE
# ======================================================

@dataclass
class LeadProfile:
    name: str | None = None
    company: str | None = None
    email: str | None = None
    role: str | None = None
    use_case: str | None = None
    team_size: str | None = None
    timeline: str | None = None
   
    def is_qualified(self):
        """Returns True if we have the minimum info (Name + Email + Use Case)"""
        return all([self.name, self.email, self.use_case])

@dataclass
class Userdata:
    lead_profile: LeadProfile

# ======================================================
# 🛠️ 3. SDR TOOLS
# ======================================================

@function_tool
async def update_lead_profile(
    ctx: RunContext[Userdata],
    name: Annotated[Optional[str], Field(description="Customer's name")] = None,
    company: Annotated[Optional[str], Field(description="Customer's company name")] = None,
    email: Annotated[Optional[str], Field(description="Customer's email address")] = None,
    role: Annotated[Optional[str], Field(description="Customer's job title")] = None,
    use_case: Annotated[Optional[str], Field(description="What they want to build or learn")] = None,
    team_size: Annotated[Optional[str], Field(description="Number of people in their team")] = None,
    timeline: Annotated[Optional[str], Field(description="When they want to start (e.g., Now, next month)")] = None,
) -> str:
    """
    ✍️ Captures lead details provided by the user during conversation.
    Only call this when the user explicitly provides information.
    """
    profile = ctx.userdata.lead_profile
   
    # Update only fields that are provided (not None)
    if name: profile.name = name
    if company: profile.company = company
    if email: profile.email = email
    if role: profile.role = role
    if use_case: profile.use_case = use_case
    if team_size: profile.team_size = team_size
    if timeline: profile.timeline = timeline
   
    print(f"📝 UPDATING LEAD: {profile}")
    return "Lead profile updated. Continue the conversation."

@function_tool
async def submit_lead_and_end(
    ctx: RunContext[Userdata],
) -> str:
    """
    💾 Saves the lead to the database and signals the end of the call.
    Call this when the user says goodbye or 'that's all'.
    """
    profile = ctx.userdata.lead_profile
   
    # Save to JSON file (Append mode)
    db_path = os.path.join(os.path.dirname(__file__), LEADS_FILE)
   
    entry = asdict(profile)
    entry["timestamp"] = datetime.now().isoformat()
   
    # Read existing, append, write back (Simple JSON DB)
    existing_data = []
    if os.path.exists(db_path):
        try:
            with open(db_path, "r") as f:
                existing_data = json.load(f)
        except: pass
   
    existing_data.append(entry)
   
    with open(db_path, "w") as f:
        json.dump(existing_data, f, indent=4)
       
    print(f"✅ LEAD SAVED TO {LEADS_FILE}")
    return f"Lead saved. Summarize the call for the user: 'Thanks {profile.name}, I have your info regarding {profile.use_case}. We will email you at {profile.email}. Goodbye!'"

# ======================================================
# 🧠 4. AGENT DEFINITION
# ======================================================

class SDRAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions=f"""
            You are 'Priya', a frank and helpful Sales Development Rep (SDR) for 'Zoho' in India.

            📘 **YOUR KNOWLEDGE BASE (FAQ):**
            {STORE_FAQ_TEXT}

            🎯 **YOUR GOAL:**
            1. Answer questions about Zoho's software suite using the FAQ.
            2. **QUALIFY THE LEAD:** Directly ask for the following details during the chat:
               - Name
               - Company / Role
               - Email
               - What are they trying to build? (Use Case)
               - Timeline (When do they need it?)

            ⚙️ **BEHAVIOR:**
            - **Start the Conversation:** Begin by asking how the user is doing, then introduce yourself and briefly explain that you can help with questions about Zoho's business software.
            - **Be Direct:** Don't beat around the bush. Answer questions straightforwardly, then ask for a detail.
            - *Example:* "Zoho One has flexible pricing. What's your team size?"
            - **Capture Data:** Use `update_lead_profile` immediately when you hear new info.
            - **Closing:** When the user is done, use `submit_lead_and_end`.

            🚫 **RESTRICTIONS:**
            - If you don't know an answer, say "I'll check with the team and email you." (Don't make up prices).
            """,
            tools=[update_lead_profile, submit_lead_and_end],
        )

# ======================================================
# 🎬 ENTRYPOINT
# ======================================================

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    print("\n" + "💼" * 25)
    print("🚀 STARTING SDR SESSION")
   
    # 1. Initialize State
    userdata = Userdata(lead_profile=LeadProfile())

    # 2. Setup Agent
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-IN-anisha",
            style="Promo",        
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        userdata=userdata,
    )
   
    # 3. Start
    await session.start(
        agent=SDRAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC()
        ),
    )

    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
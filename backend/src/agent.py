# ======================================================
# 🎯 HEALTH AND WELLNESS AGENT
# 👨‍⚕️ Developed by Anish
# 🚀 Advanced Agent Patterns & Real-world Implementation
# ======================================================

import logging
import os
import asyncio
from datetime import datetime
from typing import Annotated, Literal
from dataclasses import dataclass, field

print("\n" + "➕" * 50)
print("👨‍⚕️ HEALTH AND WELLNESS AGENT- Developed BY Anish")
print("💡 agent.py LOADED SUCCESSFULLY!")
print("➕" * 50 + "\n")

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
    tokenize,
    metrics,
    MetricsCollectedEvent,
    RunContext,
    function_tool,
)

from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
load_dotenv(".env.local")

# ======================================================
# 🧠 HEALTH & WELLNESS COMPANION
# ======================================================

@dataclass
class WellnessState:
    """Session-local wellness state for a single check-in."""
    mood: str | None = None
    energy: str | None = None
    stress: str | None = None
    objectives: list[str] = field(default_factory=list)
    session_start: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "mood": self.mood,
            "energy": self.energy,
            "stress": self.stress,
            "objectives": self.objectives,
            "session_start": self.session_start.isoformat(),
        }


@dataclass
class Userdata:
    """User session container holding wellness state."""
    wellness: WellnessState


# ======================================================
# 🛠️ WELLNESS AGENT TOOLS
# ======================================================

LOG_FILENAME = "wellness_log.json"

def get_data_file() -> str:
    """Return path to the single JSON file used to persist wellness entries."""
    base_dir = os.path.dirname(__file__)
    backend_dir = os.path.abspath(os.path.join(base_dir, ".."))
    os.makedirs(os.path.join(backend_dir, "Health-CheckIns"), exist_ok=True)
    return os.path.join(backend_dir, "Health-CheckIns", LOG_FILENAME)


def read_wellness_log() -> list:
    path = get_data_file()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except Exception:
        return []


def append_wellness_entry(entry: dict) -> str:
    path = get_data_file()
    data = read_wellness_log()
    data.append(entry)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    return path


@function_tool
async def set_mood(ctx: RunContext[Userdata], mood: Annotated[str, Field(description="User's self-reported mood")] ) -> str:
    ctx.userdata.wellness.mood = mood.strip()
    print(f"✅ MOOD SET: {ctx.userdata.wellness.mood}")
    return f"Thanks for sharing — I hear you're feeling: {ctx.userdata.wellness.mood}."


@function_tool
async def set_energy(ctx: RunContext[Userdata], energy: Annotated[str, Field(description="User's energy level (brief text or scale)")] ) -> str:
    ctx.userdata.wellness.energy = energy.strip()
    print(f"✅ ENERGY SET: {ctx.userdata.wellness.energy}")
    return f"Got it — energy: {ctx.userdata.wellness.energy}."


@function_tool
async def set_stress(ctx: RunContext[Userdata], stress: Annotated[str | None, Field(description="Anything stressing you right now? (optional)")] = None) -> str:
    ctx.userdata.wellness.stress = stress.strip() if isinstance(stress, str) else None
    print(f"✅ STRESS SET: {ctx.userdata.wellness.stress}")
    return "Thanks — noted." if ctx.userdata.wellness.stress else "No worries — noted as none."


@function_tool
async def set_objectives(ctx: RunContext[Userdata], objectives: Annotated[list[str], Field(description="1-3 objectives for today")]) -> str:
    trimmed = [o.strip() for o in objectives if o and o.strip()]
    ctx.userdata.wellness.objectives = trimmed[:3]
    print(f"✅ OBJECTIVES SET: {ctx.userdata.wellness.objectives}")
    return f"Great — I'll keep these as your objectives: {', '.join(ctx.userdata.wellness.objectives)}."


@function_tool
async def reference_previous(ctx: RunContext[Userdata]) -> str:
    entries = read_wellness_log()
    if not entries:
        return "I don't have any previous check-ins yet."
    last = entries[-1]
    mood = last.get("mood") or "unspecified mood"
    energy = last.get("energy") or "unspecified energy"
    return f"Last time you said you were feeling '{mood}' with energy: '{energy}'. How does today compare?"


@function_tool
async def complete_checkin(ctx: RunContext[Userdata]) -> str:
    w = ctx.userdata.wellness
    timestamp = datetime.now().isoformat()
    summary_parts = []
    if w.mood:
        summary_parts.append(f"mood: {w.mood}")
    if w.energy:
        summary_parts.append(f"energy: {w.energy}")
    if w.objectives:
        summary_parts.append(f"objectives: {', '.join(w.objectives)}")
    summary = "; ".join(summary_parts) if summary_parts else "No details provided."

    entry = {
        "timestamp": timestamp,
        "mood": w.mood,
        "energy": w.energy,
        "stress": w.stress,
        "objectives": w.objectives,
        "summary": summary,
    }

    path = append_wellness_entry(entry)
    print(f"🎯 Check-in saved to {path}")

    # Offer small, grounded suggestions
    suggestions = []
    if w.objectives:
        suggestions.append("Try breaking big tasks into 15–25 minute focused chunks.")
    if w.energy and any(x in w.energy.lower() for x in ["low", "tired", "drained"]):
        suggestions.append("Consider a short 5–10 minute walk or a brief rest.")
    if w.stress:
        suggestions.append("Try a quick grounding exercise: 3 deep breaths and look around for 5 things you see.")
    if not suggestions:
        suggestions.append("A small win: pick one objective and do 10 minutes on it.")

    recap = f"Summary: {summary}. Suggestions: {suggestions[0]}"
    return f"Thanks — I saved today's check-in. {recap} Does that sound right?"


class WellnessAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions=r"""
            You are a clear, grounded, supportive Health & Wellness companion. Your primary mission is to facilitate a short daily check-in, asking about mood, energy, current stressors, and 1-3 practical objectives for the day.

            Additionally, you are equipped to respond supportively if the user mentions general health issues.

            Behavior rules:
            - Ask one question at a time and keep conversations brief (2-6 turns).
            - Do NOT offer medical diagnoses or clinical advice. All suggestions must be small, practical, and non-medical. Always advise consulting a healthcare professional for specific medical concerns.
            - If the user mentions a general health issue (e.g., feeling unwell, headache, fatigue), acknowledge their concern, offer general well-being recommendations (such as staying hydrated, light stretching, ensuring a quiet environment, or taking a break), and gently advise them to rest.
            - Use empathy and reflect back the user's words.
            - When conducting a check-in, close with a short recap of their mood and 1-3 objectives, and confirm "Does this sound right?". This closing is specific to check-ins.

            Use the provided tools to record mood, energy, stress, objectives, reference previous check-ins, and to complete the check-in by saving to the JSON file.
            """,
            tools=[
                set_mood,
                set_energy,
                set_stress,
                set_objectives,
                reference_previous,
                complete_checkin,
            ],
        )


def create_empty_order():
    """Compatibility helper: return initial WellnessState wrapped in Userdata."""
    return Userdata(wellness=WellnessState())

# ======================================================
# 🧪 LIGHT TEST HELPERS
# ======================================================
def read_entries_count() -> int:
    """Return number of saved wellness entries (useful for quick checks)."""
    return len(read_wellness_log())

# ======================================================
# 🔧 SYSTEM INITIALIZATION & PREWARMING
# ======================================================
def prewarm(proc: JobProcess):
    """🔥 Preload VAD model for better performance"""
    print("🔥 Prewarming VAD model...")
    proc.userdata["vad"] = silero.VAD.load()
    print("✅ VAD model loaded successfully!")

# ======================================================
# 🎬 AGENT SESSION MANAGEMENT
# ======================================================
async def entrypoint(ctx: JobContext):
    """🎬 Main agent entrypoint - handles customer sessions"""
    ctx.log_context_fields = {"room": ctx.room.name}

    print("\n" + "🧘" * 8)
    print("🚀 Health & Wellness Companion - Daily Check-in")
    print(f"📁 Persistence file: {get_data_file()}")
    print("🎤 Ready for a short, grounded check-in")
    print("🧘" * 8 + "\n")

    # Create user session data with empty wellness state
    userdata = create_empty_order()
    
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"\n🆕 NEW CHECK-IN SESSION: {session_id}")
    print(f"📝 Past entries: {read_entries_count()}\n")

    # Create session with userdata
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
            llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-matthew",
            style="Conversation",
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        userdata=userdata,  # Pass userdata to session
    )

    # Metrics collection
    usage_collector = metrics.UsageCollector()
    @session.on("metrics_collected")
    def _on_metrics(ev: MetricsCollectedEvent):
        usage_collector.collect(ev.metrics)

    await session.start(
        agent=WellnessAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC()
        ),
    )

    # session has ended — check userdata and save if there's meaningful data
    w = userdata.wellness
    has_data = any([w.mood, w.energy, w.stress, w.objectives])
    if has_data:
        timestamp = datetime.now().isoformat()
        summary_parts = []
        if w.mood: summary_parts.append(f"mood: {w.mood}")
        if w.energy: summary_parts.append(f"energy: {w.energy}")
        if w.objectives: summary_parts.append(f"objectives: {', '.join(w.objectives)}")
        summary = "; ".join(summary_parts) if summary_parts else "No details provided."
        entry = {
            "timestamp": timestamp,
            "mood": w.mood,
            "energy": w.energy,
            "stress": w.stress,
            "objectives": w.objectives,
            "summary": summary,
        }
        path = append_wellness_entry(entry)
        print(f"🎯 Session-end check-in saved to {path}")
    else:
        print("ℹ️ No check-in data to save at session end.")

    await ctx.connect()

# ======================================================
# ⚡ APPLICATION BOOTSTRAP & LAUNCH
# ======================================================
if __name__ == "__main__":
    print("\n" + "⚡" * 25)
    print("🎬 STARTING HEALTH & WELLNESS AGENT...")
    print("👨‍⚕️ Developed By Anish Goyal")
    print("⚡" * 25 + "\n")
    
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
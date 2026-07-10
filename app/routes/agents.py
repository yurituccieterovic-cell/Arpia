"""
Agents Routes — endpoints HTTP para os agentes ADK/CrewAI.

POST /api/agents/isa-twin/run      — roda ciclo ISA-Twin
POST /api/agents/amanda-twin/run   — roda ciclo Amanda-Twin
POST /api/agents/arvore-twin/run   — roda ciclo Árvore-Twin
POST /api/agents/crew/assembleia   — dispara assembleia CrewAI com tema
GET  /api/agents/status            — status dos agentes
"""
import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/agents", tags=["agents"])


class RunRequest(BaseModel):
    prompt: Optional[str] = "Faça seu ciclo autônomo padrão."


class AssembleiaRequest(BaseModel):
    tema: str


def _run_sync(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=120)
        return loop.run_until_complete(coro)
    except Exception as e:
        return str(e)


@router.get("/status")
async def agents_status():
    from app.agents.tools.pap_tools import pap_status
    from app.agents.tools.sc_tools import sc_status
    return {
        "agents": ["ISA-Twin", "Amanda-Twin", "Arvore-Twin"],
        "crew": "Crew Tucci (ISA manager)",
        "pap": pap_status(),
        "salescockpit": sc_status(),
    }


@router.post("/isa-twin/run")
async def isa_twin_run(req: RunRequest):
    try:
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from app.agents.isa_twin import criar_isa_twin
        import uuid

        agent = criar_isa_twin()
        session_service = InMemorySessionService()
        runner = Runner(agent=agent, app_name="arpia", session_service=session_service)
        session_id = str(uuid.uuid4())

        from google.adk.sessions import Session
        await session_service.create_session(app_name="arpia", user_id="arpia", session_id=session_id)

        from google.genai.types import Part, Content
        user_msg = Content(role="user", parts=[Part(text=req.prompt)])

        response_parts = []
        async for event in runner.run_async(user_id="arpia", session_id=session_id, new_message=user_msg):
            if hasattr(event, "content") and event.content:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        response_parts.append(part.text)

        return {"ok": True, "response": "\n".join(response_parts), "agent": "ISA-Twin"}
    except Exception as e:
        raise HTTPException(500, f"ISA-Twin erro: {e}")


@router.post("/crew/assembleia")
async def crew_assembleia(req: AssembleiaRequest):
    try:
        from app.agents.crew_tucci import rodar_crew_assembleia
        # CrewAI é síncrono — roda em thread pool
        loop = asyncio.get_event_loop()
        resultado = await loop.run_in_executor(None, rodar_crew_assembleia, req.tema)
        return {"ok": True, "tema": req.tema, "resultado": resultado}
    except Exception as e:
        raise HTTPException(500, f"Crew erro: {e}")

"""
Fractal 3 — DAG de Tarefas com prevenção de ciclo via DFS.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.models.peirce import Task, TaskRelation

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class TaskCreate(BaseModel):
    title:       str
    description: str = ""
    priority:    int = 0
    parent_id:   Optional[int] = None
    source:      str = "human"
    catalog_tags: Optional[dict] = None


class RelationCreate(BaseModel):
    from_id: int
    to_id:   int
    kind:    str = "blocks"


async def _dfs_cycle_check(db: AsyncSession, start: int, target: int) -> bool:
    """
    Verifica se existe caminho de `start` até `target` no grafo de dependências.
    Se existir, adicionar a aresta target→start criaria um ciclo.
    """
    visited: set[int] = set()
    stack = [start]
    while stack:
        node = stack.pop()
        if node == target:
            return True
        if node in visited:
            continue
        visited.add(node)
        r = await db.execute(
            select(TaskRelation.to_id).where(TaskRelation.from_id == node)
        )
        stack.extend(r.scalars().all())
    return False


@router.post("/")
async def create_task(req: TaskCreate, db: AsyncSession = Depends(get_db)):
    if req.parent_id:
        parent = await db.get(Task, req.parent_id)
        if not parent:
            raise HTTPException(404, "Tarefa pai não encontrada")
    task = Task(**req.model_dump())
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return {"id": task.id, "title": task.title, "status": task.status}


@router.get("/")
async def list_tasks(
    status: Optional[str] = None,
    source: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Task)
    if status:
        q = q.where(Task.status == status)
    if source:
        q = q.where(Task.source == source)
    q = q.order_by(Task.priority.desc(), Task.created_at.asc())
    result = await db.execute(q)
    tasks = result.scalars().all()
    return [
        {"id": t.id, "title": t.title, "status": t.status,
         "priority": t.priority, "source": t.source, "parent_id": t.parent_id}
        for t in tasks
    ]


@router.patch("/{task_id}/status")
async def update_status(task_id: int, status: str, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Tarefa não encontrada")
    task.status = status
    await db.commit()
    return {"id": task.id, "status": task.status}


@router.post("/relation")
async def add_relation(req: RelationCreate, db: AsyncSession = Depends(get_db)):
    # Verifica existência
    for tid in (req.from_id, req.to_id):
        if not await db.get(Task, tid):
            raise HTTPException(404, f"Task {tid} não encontrada")

    # Prevenção de ciclo: adicionamos from→to; verificamos se to já alcança from
    would_cycle = await _dfs_cycle_check(db, req.to_id, req.from_id)
    if would_cycle:
        raise HTTPException(409, f"Ciclo detectado: adicionar {req.from_id}→{req.to_id} criaria dependência circular")

    rel = TaskRelation(from_id=req.from_id, to_id=req.to_id, kind=req.kind)
    db.add(rel)
    await db.commit()
    return {"from_id": req.from_id, "to_id": req.to_id, "kind": req.kind}


@router.get("/{task_id}/dag")
async def get_dag(task_id: int, db: AsyncSession = Depends(get_db)):
    """Retorna o subgrafo de tarefas alcançável a partir de task_id."""
    if not await db.get(Task, task_id):
        raise HTTPException(404, "Tarefa não encontrada")

    visited: dict[int, dict] = {}
    stack = [task_id]
    while stack:
        nid = stack.pop()
        if nid in visited:
            continue
        t = await db.get(Task, nid)
        if not t:
            continue
        visited[nid] = {
            "id": t.id, "title": t.title, "status": t.status,
            "priority": t.priority, "edges": []
        }
        r = await db.execute(select(TaskRelation).where(TaskRelation.from_id == nid))
        for rel in r.scalars().all():
            visited[nid]["edges"].append({"to": rel.to_id, "kind": rel.kind})
            stack.append(rel.to_id)

    return {"root": task_id, "nodes": list(visited.values())}

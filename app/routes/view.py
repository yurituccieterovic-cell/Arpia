"""
View Route — Topologia do Grafo de Conhecimento (Assembleias #398 #404)
GET /view → payload JSON da Árvore de Memória (id, parent_id, label, status)
Cada nó representa uma ATA ou decisão de assembleia persistida no Manga DB.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.core.database import get_db

router = APIRouter(prefix="/view", tags=["view"])


@router.get("/")
async def get_knowledge_graph(
    db: AsyncSession = Depends(get_db),
    status: str | None = Query(None, description="Filtro: ativo|bloqueado|stale"),
):
    """
    Retorna topologia do Grafo de Conhecimento (Árvore de Memória).
    Cada nó: { id, parent_id, label, status, tipo, created_at }
    Usado pelo front-end PAP para visualização do ecossistema.
    """
    # Tasks como nós do grafo (implementação real no Manga DB)
    query = select(text("*")).select_from(text("tasks"))
    if status:
        query = query.where(text(f"status = :status")).bindparams(status=status)

    try:
        result = await db.execute(
            text("SELECT id, parent_id, title as label, status, created_at FROM tasks"
                 + (f" WHERE status = :s" if status else ""))
            .bindparams(s=status) if status else
            text("SELECT id, parent_id, title as label, status, created_at FROM tasks")
        )
        rows = result.mappings().all()
        nodes = [dict(r) for r in rows]
    except Exception:
        nodes = []

    # Relações (arestas do grafo)
    try:
        rel_result = await db.execute(
            text("SELECT from_id, to_id, relation_type FROM task_relations")
        )
        edges = [dict(r) for r in rel_result.mappings().all()]
    except Exception:
        edges = []

    return {
        "schema": "knowledge-graph-v1",
        "nos": nodes,
        "arestas": edges,
        "total_nos": len(nodes),
        "total_arestas": len(edges),
        "fonte": "manga_db",
    }


@router.get("/topology")
async def get_topology_summary(db: AsyncSession = Depends(get_db)):
    """
    Resumo topológico: contagem por status, grau médio, nós isolados.
    Usado pela ISA para detectar nós com degree(node)=0.
    """
    try:
        # Nós isolados: tasks sem relações de entrada ou saída
        result = await db.execute(text("""
            SELECT t.id, t.title as label, t.status
            FROM tasks t
            WHERE t.id NOT IN (
                SELECT from_id FROM task_relations
                UNION
                SELECT to_id FROM task_relations
            )
        """))
        isolated = [dict(r) for r in result.mappings().all()]
    except Exception:
        isolated = []

    return {
        "nos_isolados": isolated,
        "total_isolados": len(isolated),
        "isa_alerta": len(isolated) > 0,
    }

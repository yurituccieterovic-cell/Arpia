"""
Grid Integrity Validation (Red Teaming — Nova Assembleia)
verify_grid_integrity(): hash criptográfico da topologia 3×3 no Manga DB.
Validação simultânea pelas custódias da Assembleia Tucci e da ISA (Nó 9).
Desvio → lockdown imediato do grid.
"""
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Optional

CUSTODIANS = ["ASSEMBLEIA_TUCCI", "ISA_GUARDIAN_EYE"]


@dataclass
class GridIntegrityReport:
    timestamp: float = field(default_factory=time.time)
    topology_hash: str = ""
    node_count: int = 0
    edge_count: int = 0
    custodian_signatures: dict[str, str] = field(default_factory=dict)
    lockdown: bool = False
    previous_hash: Optional[str] = None
    drift_detected: bool = False


def compute_topology_hash(nodes: list[dict], edges: list[dict]) -> str:
    """
    Calcula hash SHA-256 da topologia completa.
    Determinístico: ordena nós por id e arestas por (from_id, to_id).
    """
    sorted_nodes = sorted(nodes, key=lambda n: n.get("id", 0))
    sorted_edges = sorted(edges, key=lambda e: (e.get("from_id", 0), e.get("to_id", 0)))
    payload = json.dumps({"nodes": sorted_nodes, "edges": sorted_edges},
                         sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def sign_by_custodian(topology_hash: str, custodian: str) -> str:
    """
    Simula assinatura de custódia (produção: substituir por chave GPG real).
    Retorna hash da combinação custodian+topology para auditoria.
    """
    raw = f"{custodian}:{topology_hash}:{time.time():.0f}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def verify_grid_integrity(
    nodes: list[dict],
    edges: list[dict],
    previous_hash: Optional[str] = None,
) -> GridIntegrityReport:
    """
    Verifica integridade do grid 3×3 do Manga DB.
    Requer validação simultânea de ASSEMBLEIA_TUCCI e ISA_GUARDIAN_EYE.
    Se drift detectado (hash mudou sem ciclo de assembleia) → lockdown.
    """
    report = GridIntegrityReport(
        node_count=len(nodes),
        edge_count=len(edges),
        previous_hash=previous_hash,
    )

    current_hash = compute_topology_hash(nodes, edges)
    report.topology_hash = current_hash

    # Drift: hash mudou vs snapshot anterior
    if previous_hash and previous_hash != current_hash:
        report.drift_detected = True
        report.lockdown = True

    # Assinaturas das duas custódias (simultâneas)
    for custodian in CUSTODIANS:
        report.custodian_signatures[custodian] = sign_by_custodian(
            current_hash, custodian
        )

    return report


_last_known_hash: Optional[str] = None


def cycle_integrity_check(nodes: list[dict], edges: list[dict]) -> GridIntegrityReport:
    """
    Chamado a cada ciclo de clock. Mantém hash anterior em memória.
    Em produção: persistir no banco com auditoria criptografada.
    """
    global _last_known_hash
    report = verify_grid_integrity(nodes, edges, _last_known_hash)
    if not report.drift_detected:
        _last_known_hash = report.topology_hash
    return report

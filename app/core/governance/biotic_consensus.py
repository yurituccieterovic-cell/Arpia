# app/core/governance/biotic_consensus.py
# Mandatado pela Assembleia #414 — Auditoria Fractal PAP
# ProveBioticIntegrity — validação de integridade dos componentes bióticos
# Logs de Assembleia+ISA só persistem se multiassinatura humana+ISA+bebê_clean válida

import hashlib
import json
from datetime import datetime
from typing import Optional


BIOTIC_RANGES = {
    "temperatura_c": (18.0, 30.0),
    "ph": (6.5, 8.0),
    "lux": (10.0, 5000.0),
    "umidade_pct": (30.0, 90.0),
}


def _in_range(value: float, limits: tuple) -> bool:
    return limits[0] <= value <= limits[1]


def prove_biotic_integrity(
    host_metrics: dict,
    origem: str,
    schema_version: str,
    human_signature: str,
    isa_signature: str,
    bebe_clean_hash: str,
) -> dict:
    """
    ProveBioticIntegrity — mandatado Assembleia #414.
    Valida que os componentes bióticos do ecossistema estão em estado verificável
    antes de aceitar qualquer log de Assembleia ou ISA no Manga DB.
    Requer multiassinatura: humano (Yuri) + ISA + bebê_clean firmware.
    """
    errors = []

    for field, limits in BIOTIC_RANGES.items():
        if field in host_metrics:
            val = float(host_metrics[field])
            if not _in_range(val, limits):
                errors.append(f"{field}={val} fora do range {limits}")

    if not origem or origem not in ("assembleia", "isa_cycle", "mc_walk", "manual"):
        errors.append(f"origem inválida: '{origem}'")

    if not schema_version:
        errors.append("schema_version ausente")

    signatures_provided = all([human_signature, isa_signature, bebe_clean_hash])
    if not signatures_provided:
        errors.append("multiassinatura incompleta — humano+ISA+bebê_clean obrigatórios")

    composite = f"{human_signature}:{isa_signature}:{bebe_clean_hash}"
    audit_hash = hashlib.sha256(composite.encode()).hexdigest()

    if errors:
        return {
            "status": "REJECTED",
            "errors": errors,
            "audit_hash": audit_hash,
            "ts": datetime.utcnow().isoformat()
        }

    return {
        "status": "APPROVED",
        "origem": origem,
        "schema_version": schema_version,
        "biotic_metrics_verified": list(host_metrics.keys()),
        "audit_hash": audit_hash,
        "ts": datetime.utcnow().isoformat()
    }


def generate_audit_log(data: dict, proof: dict) -> dict:
    """Gera log auditável para persistência no Manga DB após aprovação biótica."""
    if proof.get("status") != "APPROVED":
        raise PermissionError("Tentativa de persistir log sem aprovação biótica válida.")

    payload = {
        "data": data,
        "biotic_proof": proof,
        "log_hash": hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest(),
        "created_at": datetime.utcnow().isoformat()
    }
    return payload

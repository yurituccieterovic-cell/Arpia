# app/core/aquarium_security.py
# Atualizado pela Assembleia #414 — Cadeia de Custódia mandatada
# Segurança do aquário: dedup + validação schema + barreira tag-salad + verificação firmware

import hashlib
import json
from datetime import datetime
from typing import Any, Optional


REQUIRED_SCHEMA_FIELDS = {"specie", "origin", "ts"}
_insert_log: list[dict] = []


def _is_tag_salad(tags: list) -> bool:
    """Barreira contra tag-salad vazio ou semanticamente nulo."""
    if not tags:
        return True
    meaningful = [t for t in tags if t and len(str(t).strip()) > 1]
    return len(meaningful) == 0


def validate_schema(payload: dict) -> tuple[bool, list[str]]:
    missing = [f for f in REQUIRED_SCHEMA_FIELDS if f not in payload]
    if missing:
        return False, [f"campo obrigatório ausente: {f}" for f in missing]
    if "tags" in payload and _is_tag_salad(payload.get("tags", [])):
        return False, ["barreira tag-salad: tags vazias ou semanticamente nulas"]
    return True, []


def dedup_check(payload: dict, existing_hashes: set) -> tuple[bool, str]:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    content_hash = hashlib.sha256(canonical.encode()).hexdigest()
    if content_hash in existing_hashes:
        return True, content_hash
    return False, content_hash


def verify_firmware_before_boot(firmware_manifest: dict) -> dict:
    """
    Verificação de firmware antes do boot — cadeia de custódia.
    Nenhum componente eletrônico de hardware entra na mesa de nascimento sem validação.
    """
    required = {"version", "hash", "boot_mode"}
    missing = required - set(firmware_manifest.keys())
    if missing:
        return {
            "status": "BLOCKED",
            "reason": f"firmware_manifest incompleto: {missing}",
            "ts": datetime.utcnow().isoformat()
        }

    if firmware_manifest.get("boot_mode") != "BEBE_CLEAN":
        return {
            "status": "BLOCKED",
            "reason": "boot_mode não é BEBE_CLEAN",
            "ts": datetime.utcnow().isoformat()
        }

    return {
        "status": "CLEARED",
        "firmware_version": firmware_manifest["version"],
        "firmware_hash": firmware_manifest["hash"],
        "ts": datetime.utcnow().isoformat()
    }


def custody_insert(payload: dict, existing_hashes: set, firmware_manifest: Optional[dict] = None) -> dict:
    """
    Insert via cadeia de custódia completa:
    1. Dedup — rejeita duplicatas
    2. Validação schema — campos obrigatórios + barreira tag-salad
    3. Verificação firmware (se fornecido)
    """
    is_dup, content_hash = dedup_check(payload, existing_hashes)
    if is_dup:
        return {"status": "REJECTED", "reason": "duplicata detectada", "hash": content_hash}

    valid, errors = validate_schema(payload)
    if not valid:
        return {"status": "REJECTED", "reason": "schema inválido", "errors": errors}

    if firmware_manifest is not None:
        fw_result = verify_firmware_before_boot(firmware_manifest)
        if fw_result["status"] != "CLEARED":
            return {"status": "REJECTED", "reason": "firmware não verificado", "firmware": fw_result}

    entry = {
        **payload,
        "content_hash": content_hash,
        "custody_ts": datetime.utcnow().isoformat()
    }
    _insert_log.append({"hash": content_hash, "ts": entry["custody_ts"]})
    existing_hashes.add(content_hash)

    return {"status": "ACCEPTED", "content_hash": content_hash, "entry": entry}

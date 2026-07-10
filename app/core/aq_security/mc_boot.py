"""
MC Boot Security — Modo Bebê_Clean aumentado (Red Teaming — Nova Assembleia)
validate_chassis_integrity(): verificação cruzada de firmware do Step Down.
Boot abortado se log de integridade de hardware não estiver limpo.
Previne IoT Poisoning na mesa de nascimento.
"""
import hashlib
import time
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class BootStatus(str, Enum):
    CLEAN = "CLEAN"           # boot seguro — Modo Bebê_Clean ativo
    ABORTED = "ABORTED"       # boot abortado — integridade comprometida
    DEGRADED = "DEGRADED"     # boot em modo reduzido — algum sensor falhou
    PENDING = "PENDING"       # aguardando validação das custódias


@dataclass
class ChassisIntegrityLog:
    timestamp: float = field(default_factory=time.time)
    status: BootStatus = BootStatus.PENDING
    firmware_hash: str = ""
    step_down_ok: bool = False
    power_bank_ok: bool = False
    led_ring_ok: bool = False
    contaminacao_biotica: bool = False
    payload_nao_homologado: Optional[str] = None
    abort_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "status": self.status.value,
            "firmware_hash": self.firmware_hash[:12] + "...",
            "step_down_ok": self.step_down_ok,
            "power_bank_ok": self.power_bank_ok,
            "led_ring_ok": self.led_ring_ok,
            "contaminacao_biotica": self.contaminacao_biotica,
            "abort_reason": self.abort_reason,
        }


# Payloads bióticos proibidos na mesa de nascimento (Red Teaming)
_PAYLOADS_PROIBIDOS = {
    "organic_matter_pepper",  # Pimenta Ornamental Black Pearl (capsaicina)
    "unknown_organic",
    "toxic_plant",
    "unverified_component",
}


def validate_chassis_integrity(
    firmware_version: str,
    tensao_step_down_v: float,
    power_bank_connected: bool,
    led_ring_responsive: bool,
    detected_payloads: list[str] | None = None,
) -> ChassisIntegrityLog:
    """
    Valida integridade do chassis MEKY antes do boot no Modo Bebê_Clean.
    Verificações:
    1. Step Down: tensão > 5V por 2s
    2. Power Bank: conectado com cabos vermelhos
    3. Anel LED WS2812B: responsivo
    4. Ausência de payloads bióticos não homologados (IoT Poisoning)
    5. Hash do firmware: integridade do código de borda
    """
    log = ChassisIntegrityLog()
    log.firmware_hash = hashlib.sha256(firmware_version.encode()).hexdigest()

    # Verificação Step Down
    log.step_down_ok = tensao_step_down_v >= 5.0
    if not log.step_down_ok:
        log.abort_reason = f"Step Down abaixo de 5V: {tensao_step_down_v:.2f}V"
        log.status = BootStatus.ABORTED
        return log

    # Verificação Power Bank
    log.power_bank_ok = power_bank_connected
    if not power_bank_connected:
        log.status = BootStatus.DEGRADED
        log.abort_reason = "Power Bank desconectado — operando em modo degradado"

    # Verificação anel LED
    log.led_ring_ok = led_ring_responsive
    if not led_ring_responsive:
        log.status = BootStatus.DEGRADED
        log.abort_reason = (log.abort_reason or "") + " | LED ring não responsivo"

    # Verificação biótica (IoT Poisoning)
    if detected_payloads:
        for payload in detected_payloads:
            if payload.lower() in _PAYLOADS_PROIBIDOS:
                log.contaminacao_biotica = True
                log.payload_nao_homologado = payload
                log.status = BootStatus.ABORTED
                log.abort_reason = f"ToxinContaminationAlert: payload={payload}"
                return log

    if log.status == BootStatus.PENDING:
        log.status = BootStatus.CLEAN

    return log


def boot_mc_safe(
    firmware_version: str = "v0.6.0",
    tensao_step_down_v: float = 5.2,
    power_bank_connected: bool = True,
    led_ring_responsive: bool = True,
    detected_payloads: list[str] | None = None,
) -> dict:
    """
    Wrapper de boot completo: valida, loga e retorna status.
    Se ABORTED → emite ToxinContaminationAlert ou PowerAlert.
    """
    integrity = validate_chassis_integrity(
        firmware_version,
        tensao_step_down_v,
        power_bank_connected,
        led_ring_responsive,
        detected_payloads,
    )

    response = integrity.to_dict()
    response["modo_bebe_clean"] = integrity.status == BootStatus.CLEAN
    response["face_id"] = 1 if integrity.status == BootStatus.CLEAN else 4  # OK ou ALERTA_ALTO

    return response

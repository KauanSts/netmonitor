"""Verificação pontual de conectividade. Use apenas em destinos autorizados."""
import ipaddress
import math
import platform
import re
import subprocess


def validate_target(target: str) -> str:
    """Aceita IPv4 ou hostname DNS ASCII, sem opções, URLs ou IPv6."""
    if not isinstance(target, str) or not target or target != target.strip():
        raise ValueError("Informe um IPv4 ou domínio válido.")
    try:
        return str(ipaddress.IPv4Address(target))
    except ipaddress.AddressValueError:
        pass
    if re.fullmatch(r"[0-9.]+", target):
        raise ValueError("IPv4 inválido.")
    hostname = target[:-1] if target.endswith(".") else target
    labels = hostname.split(".")
    if len(hostname) > 253 or not all(
        re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
        for label in labels
    ):
        raise ValueError("Domínio inválido.")
    return target


def check_connectivity(target: str, timeout: float = 2.0) -> dict:
    """Retorna target, status, latency_ms e error.

    Status: online, offline, timeout ou error. Entrada inválida levanta ValueError.
    Para respostas '<1 ms', latency_ms é o limite superior (1.0), acompanhado
    de latency_is_upper_bound=True. Ausência de RTT não impede status online.
    """
    target = validate_target(target)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 60:
        raise ValueError("Timeout deve ser um número entre 0 e 60 segundos.")
    system = platform.system()
    result = {"target": target, "status": "error", "latency_ms": None,
              "latency_is_upper_bound": False, "error": None}
    if system == "Windows":
        command = ["ping", "-4", "-n", "1", "-w", str(math.ceil(timeout * 1000)), target]
    elif system == "Linux":
        command = ["ping", "-4", "-n", "-c", "1", "-W", str(math.ceil(timeout)), target]
    else:
        result["error"] = f"Sistema não suportado: {system}"
        return result
    try:
        process = subprocess.run(command, capture_output=True, text=True,
                                 errors="replace", timeout=timeout + 1, check=False)
    except subprocess.TimeoutExpired:
        result.update(status="timeout", error="Tempo limite do processo excedido.")
        return result
    except OSError as exc:
        result["error"] = f"Não foi possível executar ping: {exc}"
        return result
    output = process.stdout + "\n" + process.stderr
    match = re.search(r"(?:time|tempo)\s*([=<])\s*(\d+(?:[.,]\d+)?)\s*ms", output, re.I)
    # Windows pode retornar código zero para mensagens de destino inacessível.
    reply = re.search(r"\b(?:ttl|hlim)\s*[=:]\s*\d+", output, re.I)
    if process.returncode == 0 and (match or reply):
        result["status"] = "online"
        if match:
            result["latency_ms"] = float(match[2].replace(",", "."))
            result["latency_is_upper_bound"] = match[1] == "<"
    elif re.search(r"timed?\s*out|tempo.*esgotado|esgotado.*tempo|100%\s*(?:packet loss|de perda)", output, re.I):
        result.update(status="timeout", error="Nenhuma resposta dentro do prazo.")
    elif process.returncode in (0, 1):
        result.update(status="offline", error="O destino não respondeu ao ping.")
    else:
        result["error"] = "Falha ao executar ping ou resolver o destino."
    return result

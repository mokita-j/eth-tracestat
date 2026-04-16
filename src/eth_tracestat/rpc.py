"""JSON-RPC helpers for Ethereum nodes."""

import requests


def rpc(url: str, method: str, params: list, timeout: int = 300) -> object:
    resp = requests.post(
        url,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )
    resp.raise_for_status()
    body = resp.json()
    if "error" in body:
        raise RuntimeError(f"RPC error {body['error']['code']}: {body['error']['message']}")
    return body["result"]


def latest_block(url: str) -> int:
    return int(rpc(url, "eth_blockNumber", []), 16)

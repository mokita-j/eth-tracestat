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


def rpc_batch(url: str, calls: list[tuple[str, list]], timeout: int = 300) -> list:
    """Send multiple JSON-RPC calls in a single HTTP request."""
    payload = [
        {"jsonrpc": "2.0", "id": i, "method": method, "params": params}
        for i, (method, params) in enumerate(calls)
    ]
    resp = requests.post(
        url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )
    resp.raise_for_status()
    results = sorted(resp.json(), key=lambda r: r["id"])
    for r in results:
        if "error" in r:
            raise RuntimeError(f"RPC error {r['error']['code']}: {r['error']['message']}")
    return [r["result"] for r in results]


def latest_block(url: str) -> int:
    return int(rpc(url, "eth_blockNumber", []), 16)

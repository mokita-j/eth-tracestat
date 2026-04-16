"""EVM constants and address normalization."""

CALL_OPS_OWN_STORAGE = {"CALL", "STATICCALL"}
CALL_OPS_INHERIT_STORAGE = {"DELEGATECALL", "CALLCODE"}
CREATE_OPS = {"CREATE", "CREATE2"}

# Precompile addresses — pre-warmed since EIP-2929 (Berlin) / EIP-4844 (Cancun).
# Calls to these always pay the warm cost, so they're excluded from account
# distributions that measure warming opportunity.
PRECOMPILES = {"0x" + f"{i:040x}" for i in range(1, 0x0b)}  # 0x01..0x0a


def normalize_addr(raw: str) -> str:
    """Normalize a hex string (as pulled from the stack) to a 20-byte 0x address."""
    h = raw.lower()
    if h.startswith("0x"):
        h = h[2:]
    if len(h) < 40:
        h = h.zfill(40)
    else:
        h = h[-40:]
    return "0x" + h

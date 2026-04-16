"""Pure trace processing: JSON in, structured counts out. No I/O."""

from collections import defaultdict
from dataclasses import dataclass, field

from .evm import (
    CALL_OPS_INHERIT_STORAGE,
    CALL_OPS_OWN_STORAGE,
    CREATE_OPS,
    PRECOMPILES,
    normalize_addr,
)


@dataclass
class SlotAccess:
    sload_count: int = 0
    sstore_count: int = 0

    @property
    def total(self) -> int:
        return self.sload_count + self.sstore_count


@dataclass
class BlockCounts:
    """Full per-key counts for a single block."""
    block_num: int
    n_txs: int
    # Per-block: (contract, slot) -> {sload, sstore}
    slot_ops: dict[tuple[str, str], SlotAccess] = field(default_factory=dict)
    # Per-block: contract -> call count
    account_calls: dict[str, int] = field(default_factory=dict)
    # Per-tx: (tx_idx, contract, slot) -> {sload, sstore}
    tx_slot_access: dict[tuple[int, str, str], SlotAccess] = field(default_factory=dict)
    # Per-tx: (tx_idx, contract) -> call count
    tx_account_call: dict[tuple[int, str], int] = field(default_factory=dict)


def _get_slot_access(d: dict, key) -> SlotAccess:
    """Get or create a SlotAccess entry in a dict."""
    if key not in d:
        d[key] = SlotAccess()
    return d[key]


def process_tx_trace(
    tx_idx: int,
    tx_trace: dict,
    entry_addr: str,
    counts: BlockCounts,
) -> None:
    """Process a single tx's structLogs and accumulate into counts."""
    result = tx_trace.get("result", tx_trace)
    struct_logs = result.get("structLogs", [])

    storage_stack = [entry_addr]

    if entry_addr not in PRECOMPILES:
        counts.account_calls[entry_addr] = counts.account_calls.get(entry_addr, 0) + 1
        key = (tx_idx, entry_addr)
        counts.tx_account_call[key] = counts.tx_account_call.get(key, 0) + 1

    prev_op = None
    prev_stack = None
    prev_depth = 1
    create_counter = 0

    for step in struct_logs:
        op = step.get("op", "")
        depth = step.get("depth", 1)
        stack = step.get("stack", [])

        # Record account calls (excluding precompiles).
        if op in CALL_OPS_OWN_STORAGE or op in CALL_OPS_INHERIT_STORAGE:
            if len(stack) >= 2:
                target = normalize_addr(stack[-2])
                if target not in PRECOMPILES:
                    counts.account_calls[target] = counts.account_calls.get(target, 0) + 1
                    key = (tx_idx, target)
                    counts.tx_account_call[key] = counts.tx_account_call.get(key, 0) + 1

        # Maintain storage context stack.
        if depth > prev_depth:
            if prev_op in CALL_OPS_OWN_STORAGE and prev_stack and len(prev_stack) >= 2:
                storage_stack.append(normalize_addr(prev_stack[-2]))
            elif prev_op in CALL_OPS_INHERIT_STORAGE:
                storage_stack.append(storage_stack[-1])
            elif prev_op in CREATE_OPS:
                create_counter += 1
                storage_stack.append(f"0xcreate_tx{tx_idx}_{create_counter}")
            else:
                storage_stack.append(storage_stack[-1])
        elif depth < prev_depth:
            while len(storage_stack) > depth:
                storage_stack.pop()

        if op in ("SLOAD", "SSTORE") and stack:
            raw_slot = stack[-1]
            slot_hex = raw_slot.lstrip("0x").zfill(64).lower()
            contract = storage_stack[-1] if storage_stack else "unknown"

            block_access = _get_slot_access(counts.slot_ops, (contract, slot_hex))
            tx_access = _get_slot_access(counts.tx_slot_access, (tx_idx, contract, slot_hex))

            if op == "SLOAD":
                block_access.sload_count += 1
                tx_access.sload_count += 1
            else:
                block_access.sstore_count += 1
                tx_access.sstore_count += 1

        prev_op = op
        prev_stack = stack
        prev_depth = depth


def process_block_traces(
    block_data: dict,
    traces: list[dict],
    block_num: int,
) -> BlockCounts:
    """Process all tx traces in a block. Pure function: JSON in, BlockCounts out."""
    tx_entry_addrs = []
    for i, tx in enumerate(block_data.get("transactions", [])):
        to = tx.get("to")
        tx_entry_addrs.append(to.lower() if to else f"0xcreate_tx{i}")

    counts = BlockCounts(block_num=block_num, n_txs=len(traces))

    for tx_idx, tx_trace in enumerate(traces):
        entry = tx_entry_addrs[tx_idx] if tx_idx < len(tx_entry_addrs) else "unknown"
        process_tx_trace(tx_idx, tx_trace, entry, counts)

    return counts

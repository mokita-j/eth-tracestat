"""Terminal text reporting."""

from collections import defaultdict


def print_result(r: dict):
    print(f"\n{'═'*58}")
    print(f"  Block {r['block']}")
    print(f"{'═'*58}")
    print(f"  Transactions            : {r['total_txs']:>8,}")
    print(f"  Unique (contract,slot)  : {r['total_unique_slots']:>8,}")
    print(f"  Multi-access slots (N≥2): {r['multi_access_slots']:>8,}")
    print(f"  Multi-access rate       : {r['multi_access_rate']:>8.1%}")
    print(f"  Unique accounts called  : {r['total_unique_accounts']:>8,}")
    print(f"  Multi-call accounts(N≥2): {r['multi_call_accounts']:>8,}")
    print(f"  Multi-call rate         : {r['multi_call_rate']:>8.1%}")

    print(f"\n  N(s,B) distribution (SLOAD+SSTORE ops per (contract,slot) in block)")
    print(f"  {'N':>4}  {'slots':>8}  {'% of total':>10}  histogram")
    print(f"  {'─'*4}  {'─'*8}  {'─'*10}  {'─'*30}")
    total = r['total_unique_slots']
    for n, count in sorted(r['n_distribution'].items()):
        pct = count / total if total else 0
        bar = '▓' * int(pct * 60)
        print(f"  {n:>4}  {count:>8,}  {pct:>9.1%}  {bar}")

    print(f"\n  N(c,B) distribution (calls per account in block)")
    print(f"  {'N':>4}  {'accts':>8}  {'% of total':>10}  histogram")
    print(f"  {'─'*4}  {'─'*8}  {'─'*10}  {'─'*30}")
    total_a = r['total_unique_accounts']
    for n, count in sorted(r['account_n_distribution'].items()):
        pct = count / total_a if total_a else 0
        bar = '▓' * int(pct * 60)
        print(f"  {n:>4}  {count:>8,}  {pct:>9.1%}  {bar}")

    print(f"\n  Top (contract, slot) pairs by ops")
    print(f"  {'Address':<42}  {'Slot prefix':<14}  N")
    print(f"  {'─'*42}  {'─'*14}  {'─'*4}")
    for s in r['top_shared_slots']:
        print(f"  {s['address']:<42}  {s['slot'][:12]}…  {s['n_ops']}")

    print(f"\n  Top accounts by calls")
    print(f"  {'Address':<42}  N")
    print(f"  {'─'*42}  {'─'*4}")
    for a in r['top_shared_accounts']:
        print(f"  {a['address']:<42}  {a['n_calls']}")

    print(f"\n  N(s,T) distribution (per-tx slot accesses)")
    print(f"  {'N':>4}  {'(tx,slot)':>10}  {'% of total':>10}  histogram")
    print(f"  {'─'*4}  {'─'*10}  {'─'*10}  {'─'*30}")
    total_st = r['total_tx_slot_entries']
    for n, count in sorted(r['tx_slot_distribution'].items()):
        pct = count / total_st if total_st else 0
        bar = '▓' * int(pct * 60)
        print(f"  {n:>4}  {count:>10,}  {pct:>9.1%}  {bar}")

    print(f"\n  N(c,T) distribution (per-tx account calls)")
    print(f"  {'N':>4}  {'(tx,acct)':>10}  {'% of total':>10}  histogram")
    print(f"  {'─'*4}  {'─'*10}  {'─'*10}  {'─'*30}")
    total_ct = r['total_tx_account_entries']
    for n, count in sorted(r['tx_account_distribution'].items()):
        pct = count / total_ct if total_ct else 0
        bar = '▓' * int(pct * 60)
        print(f"  {n:>4}  {count:>10,}  {pct:>9.1%}  {bar}")


def print_summary(results: list):
    if len(results) < 2:
        return
    n = len(results)
    print(f"\n{'═'*58}")
    print(f"  Summary across {n} blocks")
    print(f"{'═'*58}")

    def avg(key):
        return sum(r[key] for r in results) / n

    print(f"  Avg transactions/block  : {avg('total_txs'):>8.1f}")
    print(f"  Avg unique slots/block  : {avg('total_unique_slots'):>8.1f}")
    print(f"  Avg multi-access slots  : {avg('multi_access_slots'):>8.1f}")
    print(f"  Avg multi-access rate   : {avg('multi_access_rate'):>8.1%}")
    print(f"  Avg unique accounts     : {avg('total_unique_accounts'):>8.1f}")
    print(f"  Avg multi-call accounts : {avg('multi_call_accounts'):>8.1f}")
    print(f"  Avg multi-call rate     : {avg('multi_call_rate'):>8.1%}")

    agg: dict = defaultdict(int)
    for r in results:
        for n_val, count in r['n_distribution'].items():
            agg[n_val] += count

    print(f"\n  Aggregated N(s,B) distribution across all blocks")
    total_agg = sum(agg.values())
    print(f"  {'N':>4}  {'slots':>10}  {'%':>8}")
    for n_val in sorted(agg):
        pct = agg[n_val] / total_agg
        print(f"  {n_val:>4}  {agg[n_val]:>10,}  {pct:>7.2%}")

    agg_acc: dict = defaultdict(int)
    for r in results:
        for n_val, count in r['account_n_distribution'].items():
            agg_acc[n_val] += count

    print(f"\n  Aggregated N(c,B) distribution across all blocks")
    total_agg_acc = sum(agg_acc.values())
    print(f"  {'N':>4}  {'accts':>10}  {'%':>8}")
    for n_val in sorted(agg_acc):
        pct = agg_acc[n_val] / total_agg_acc
        print(f"  {n_val:>4}  {agg_acc[n_val]:>10,}  {pct:>7.2%}")

    agg_st: dict = defaultdict(int)
    for r in results:
        for n_val, count in r['tx_slot_distribution'].items():
            agg_st[n_val] += count

    print(f"\n  Aggregated N(s,T) distribution (per-tx slot accesses)")
    total_agg_st = sum(agg_st.values())
    print(f"  {'N':>4}  {'(tx,slot)':>10}  {'%':>8}")
    for n_val in sorted(agg_st):
        pct = agg_st[n_val] / total_agg_st
        print(f"  {n_val:>4}  {agg_st[n_val]:>10,}  {pct:>7.2%}")

    agg_ct: dict = defaultdict(int)
    for r in results:
        for n_val, count in r['tx_account_distribution'].items():
            agg_ct[n_val] += count

    print(f"\n  Aggregated N(c,T) distribution (per-tx account calls)")
    total_agg_ct = sum(agg_ct.values())
    print(f"  {'N':>4}  {'(tx,acct)':>10}  {'%':>8}")
    for n_val in sorted(agg_ct):
        pct = agg_ct[n_val] / total_agg_ct
        print(f"  {n_val:>4}  {agg_ct[n_val]:>10,}  {pct:>7.2%}")

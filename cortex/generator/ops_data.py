"""Generate Cortex Bank's operational graph (~1M nodes, ~5M relationships) with planted fraud rings.

Usage: python -m generator.ops_data [--scale 1.0]   (run from cortex/)
Outputs CSVs for falkordb-bulk-insert into data/ops/, and the fraud-ring answer key into data/ops_gold.json.
Deterministic: the same seed always produces the same bank.
"""
import argparse
import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "ops"
SEED = 1926

BASE = {"Customer": 250_000, "Account": 300_000, "Device": 180_000, "Address": 170_000,
        "IP": 100_000, "Merchant": 5_000, "Branch": 40}
TRANSFERS_PER_ACCOUNT = 11
PAYMENTS_PER_ACCOUNT = 2
RINGS = 60


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=1.0, help="0.05 = small test graph")
    scale = ap.parse_args().scale
    rnd = random.Random(SEED)
    n = {k: max(5, int(v * scale)) if k != "Branch" else v for k, v in BASE.items()}
    OUT.mkdir(parents=True, exist_ok=True)

    def w(name, header, rows):
        with open(OUT / f"{name}.csv", "w", newline="") as f:
            cw = csv.writer(f)
            cw.writerow(header)
            cw.writerows(rows)

    segs = ["Retail", "Retail", "Retail", "Premier", "SME", "Wealth"]
    risk = ["Low"] * 7 + ["Medium"] * 2 + ["High"]
    w("Branch", ["id", "name", "region"], ((f"B{i}", f"Branch {i:02d}", rnd.choice(["North", "South", "East", "West", "Harbour"])) for i in range(n["Branch"])))
    w("Customer", ["id", "segment", "risk_rating", "since"],
      ((f"C{i}", rnd.choice(segs), rnd.choice(risk), rnd.randint(1960, 2026)) for i in range(n["Customer"])))
    w("Device", ["id", "type"], ((f"D{i}", rnd.choice(["iOS", "Android", "Web"])) for i in range(n["Device"])))
    w("Address", ["id", "postcode"], ((f"AD{i}", f"PA{rnd.randint(1, 99)} {rnd.randint(1, 9)}XZ") for i in range(n["Address"])))
    w("IP", ["id", "country"], ((f"IP{i}", rnd.choice(["GB"] * 9 + ["NL", "AE", "CY"])) for i in range(n["IP"])))
    w("Merchant", ["id", "category"], ((f"M{i}", rnd.choice(["Grocery", "Fuel", "Travel", "Online", "Gambling", "Crypto"])) for i in range(n["Merchant"])))

    nc, na = n["Customer"], n["Account"]
    acct_owner = [i if i < nc else rnd.randrange(nc) for i in range(na)]
    w("Account", ["id", "type", "branch"],
      ((f"A{i}", rnd.choice(["Current", "Current", "Savings", "Business"]), f"B{rnd.randrange(n['Branch'])}") for i in range(na)))
    w("OWNS", ["src", "dst"], ((f"C{o}", f"A{i}") for i, o in enumerate(acct_owner)))

    # Normal behaviour: customers mostly have their own device and address.
    uses, lives, logs = [], [], []
    for c in range(nc):
        uses.append((f"C{c}", f"D{rnd.randrange(n['Device'])}"))
        if rnd.random() < 0.4:
            uses.append((f"C{c}", f"D{rnd.randrange(n['Device'])}"))
        lives.append((f"C{c}", f"AD{rnd.randrange(n['Address'])}"))
    for d in range(n["Device"]):
        logs.append((f"D{d}", f"IP{rnd.randrange(n['IP'])}"))

    transfers = []
    for a in range(na):
        for _ in range(rnd.randint(TRANSFERS_PER_ACCOUNT // 2, TRANSFERS_PER_ACCOUNT * 3 // 2)):
            transfers.append((f"A{a}", f"A{rnd.randrange(na)}", round(rnd.lognormvariate(5, 1.2), 2), rnd.randint(1, 365)))
    payments = [(f"A{rnd.randrange(na)}", f"M{rnd.randrange(n['Merchant'])}", round(rnd.lognormvariate(3.5, 1), 2))
                for _ in range(na * PAYMENTS_PER_ACCOUNT)]

    # Plant fraud rings: shared device + shared address + circular sub-10,000 transfers (structuring).
    gold, used = [], set()
    for r in range(RINGS if scale >= 0.2 else 5):
        size = rnd.randint(5, 12)
        members = []
        while len(members) < size:
            c = rnd.randrange(nc)
            if c not in used and c < na:
                used.add(c)
                members.append(c)
        dev, addr, ip = f"D{rnd.randrange(n['Device'])}", f"AD{rnd.randrange(n['Address'])}", f"IP{rnd.randrange(n['IP'])}"
        for c in members:
            uses.append((f"C{c}", dev))
            if rnd.random() < 0.7:
                lives.append((f"C{c}", addr))
        logs.append((dev, ip))
        accts = [f"A{c}" for c in members]  # account i is owned by customer i for i < nc
        for i, a in enumerate(accts):
            transfers.append((a, accts[(i + 1) % len(accts)], round(rnd.uniform(9000, 9990), 2), rnd.randint(300, 365)))
        gold.append({"ring": r, "customers": [f"C{c}" for c in members], "accounts": accts, "shared_device": dev, "shared_address": addr})

    w("USES_DEVICE", ["src", "dst"], uses)
    w("LIVES_AT", ["src", "dst"], lives)
    w("LOGGED_FROM", ["src", "dst"], logs)
    w("TRANSFER", ["src", "dst", "amount", "day"], transfers)
    w("PAID", ["src", "dst", "amount"], payments)
    (ROOT / "data" / "ops_gold.json").write_text(json.dumps(gold))
    nodes = sum(n.values())
    rels = len(acct_owner) + len(uses) + len(lives) + len(logs) + len(transfers) + len(payments)
    print(f"nodes={nodes:,} relationships={rels:,} rings={len(gold)}")


if __name__ == "__main__":
    main()

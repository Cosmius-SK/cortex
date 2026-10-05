"""Generate deterministic, typed synthetic CSVs for the FalkorDB bulk loader, plus manifest.json (counts + SHA-256).

Streams rows with csv.writer (no DataFrames). Node ids are globally unique "Label:index" strings; edge ids are
"TYPE:index" in the rid property. Edges reference stored ids, never database-internal ids.

  python scripts/generate_seed.py --model examples/grc.model.json --factor 0.01 --out data/smoke
"""
import argparse
import csv
import random
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import Timer, die, now, read_json, sha256, write_json  # noqa: E402

TYPES = {"STRING", "INT", "DOUBLE", "BOOLEAN"}
VERSION = "1.1"


def scaled(count, factor):
    return max(1, round(count * factor))


def rng_for(seed, name):
    return random.Random(seed * 1_000_003 + zlib.crc32(name.encode()))


def validate_model(model):
    labels = {n["label"] for n in model["nodes"]}
    errs = []
    for n in model["nodes"]:
        for p, spec in n.get("properties", {}).items():
            if p == "id":
                errs.append(f"{n['label']}: 'id' is reserved")
            if spec.get("type") not in TYPES:
                errs.append(f"{n['label']}.{p}: type {spec.get('type')} unsupported by this generator (extend it deliberately)")
    for r in model["relationships"]:
        for end in ("from", "to"):
            if r[end] not in labels:
                errs.append(f"{r['type']}: {end} label {r[end]} not defined")
        for p, spec in r.get("properties", {}).items():
            if p == "rid":
                errs.append(f"{r['type']}: 'rid' is reserved")
            if spec.get("type") not in TYPES:
                errs.append(f"{r['type']}.{p}: unsupported type {spec.get('type')}")
    return errs


def value(spec, i, rnd):
    t = spec["type"]
    if "choices" in spec:
        return rnd.choice(spec["choices"])
    if t == "STRING" and spec.get("format") == "date":  # ISO date stored as a string (portable across both engines)
        y = rnd.randint(spec.get("min_year", 2015), spec.get("max_year", 2026))
        return f"{y:04d}-{rnd.randint(1, 12):02d}-{rnd.randint(1, 28):02d}"
    if t == "STRING":
        return spec.get("pattern", "v-{i}").format(i=i)
    if t == "INT":
        return rnd.randint(spec.get("min", 0), spec.get("max", 1000))
    if t == "DOUBLE":
        return round(rnd.uniform(spec.get("min", 0.0), spec.get("max", 1.0)), 4)
    if t == "BOOLEAN":
        return "true" if rnd.random() < spec.get("p_true", 0.5) else "false"
    raise ValueError(t)


def plant_rings(spec, counts, rnd):
    """Planted rings: groups of `label` nodes that share one target per listed relationship type
    (e.g. customers sharing a phone, an address and an e-mail). Returned as a gold set for evaluation."""
    if not spec:
        return [], {}
    label, members_total = spec["label"], counts[spec["label"]]
    n_rings = max(1, round(spec["count"] * min(1.0, members_total / spec.get("reference_population", members_total))))
    lo, hi = spec.get("size", [4, 8])
    edges, rings, used = {}, [], set()
    for k in range(n_rings):
        size = rnd.randint(lo, hi)
        members = []
        while len(members) < size and len(used) < members_total:
            m = rnd.randrange(members_total)
            if m not in used:
                used.add(m)
                members.append(m)
        shared = {}
        for rel in spec["share"]:
            target_label = spec["targets"][rel]
            tgt = rnd.randrange(counts[target_label])
            shared[rel] = f"{target_label}:{tgt}"
            edges.setdefault(rel, []).extend((m, tgt) for m in members)
        rings.append({"ring": k, "members": [f"{label}:{m}" for m in members], "shared": shared})
    return rings, edges


def header(props, id_col):
    return id_col + [f"{p}:{s['type']}" for p, s in props.items()]


def generate(model, factor, out, seed=None):
    seed = model.get("seed", 1) if seed is None else seed
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    counts = {n["label"]: scaled(n["count"], factor) for n in model["nodes"]}
    files, rel_counts = [], {}
    for n in model["nodes"]:
        label, props, rnd = n["label"], n.get("properties", {}), rng_for(seed, n["label"])
        path = out / f"{label}.csv"
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(header(props, ["id:ID"]))
            for i in range(counts[label]):
                w.writerow([f"{label}:{i}"] + [value(s, i, rnd) for s in props.values()])
        files.append(("node", label, path))
    rings, ring_edges = plant_rings(model.get("rings"), counts, rng_for(seed, "rings"))
    for r in model["relationships"]:
        t, props, rnd = r["type"], r.get("properties", {}), rng_for(seed, r["type"])
        n, nf, nt = scaled(r["count"], factor), counts[r["from"]], counts[r["to"]]
        mode = r.get("mode", "random")
        hub, src_hub = r.get("hub") or {}, r.get("src_hub") or {}
        hub_frac, hub_top = hub.get("fraction", 0), max(1, int(nt * hub.get("top_fraction", 0.01)))
        src_frac, src_top = src_hub.get("fraction", 0), max(1, int(nf * src_hub.get("top_fraction", 0.01)))
        extra = ring_edges.get(t, [])
        unique = r.get("unique", model.get("unique_relationships", False))
        seen = set()
        path = out / f"{t}.csv"
        k = 0
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow([":START_ID", ":END_ID", "rid:STRING"] + [f"{p}:{s['type']}" for p, s in props.items()])

            def emit(a, b):
                nonlocal k
                w.writerow([f"{r['from']}:{a}", f"{r['to']}:{b}", f"{t}:{k}"] + [value(s, k, rnd) for s in props.values()])
                k += 1
            for i in range(n):
                if mode == "sequential":  # identifier-style: near one-to-one, neighbours occasionally share a target
                    a, b = i % nf, min(nt - 1, i * nt // n)
                    if unique and (a, b) in seen:
                        continue
                else:
                    for attempt in range(1000):  # hubs first; fall back to uniform when a hub is saturated
                        hubby = attempt < 10
                        a = rnd.randrange(src_top) if hubby and rnd.random() < src_frac else rnd.randrange(nf)
                        b = rnd.randrange(hub_top) if hubby and rnd.random() < hub_frac else rnd.randrange(nt)
                        if not unique or (a, b) not in seen:
                            break
                    else:
                        continue  # space exhausted: skip rather than create a parallel edge
                if unique:
                    seen.add((a, b))
                emit(a, b)
            for a, b in extra:  # planted ring edges
                if unique and (a, b) in seen:
                    continue
                seen.add((a, b))
                emit(a, b)
        rel_counts[t] = k
        files.append(("relationship", t, path))
    manifest = {
        "model": model.get("name"), "generator_version": VERSION, "seed": seed, "factor": factor, "generated_at": now(),
        "nodes": counts, "relationships": rel_counts,
        "totals": {"nodes": sum(counts.values()), "relationships": sum(rel_counts.values()),
                   "entities": sum(counts.values()) + sum(rel_counts.values())},
        "endpoints": {r["type"]: {"from": r["from"], "to": r["to"]} for r in model["relationships"]},
        "rings": rings,
        "files": [{"kind": k, "name": nm, "file": p.name, "bytes": p.stat().st_size, "sha256": sha256(p)} for k, nm, p in files],
    }
    write_json(out / "manifest.json", manifest)
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--factor", type=float, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int)
    a = ap.parse_args()
    model = read_json(a.model)
    errs = validate_model(model)
    if errs:
        die("Model errors:\n  " + "\n  ".join(errs))
    if Path(a.out).exists() and any(Path(a.out).iterdir()):
        die(f"{a.out} is not empty. Use a new directory so the manifest always matches its files.")
    with Timer() as t:
        m = generate(model, a.factor, a.out, a.seed)
    mb = sum(f["bytes"] for f in m["files"]) / 1e6
    print(f"Generated {m['totals']['nodes']:,} nodes + {m['totals']['relationships']:,} relationships "
          f"({m['totals']['entities']:,} entities) in {t.s:.1f}s · {mb:,.1f} MB CSV · {a.out}/manifest.json")


if __name__ == "__main__":
    main()

"""S02: reinforcement-learning scheduler (ALGORITHM_DESIGN.md 4, docs/S02_IMPLEMENTATION_PLAN.md).

Episode = one instance; action = a (ready task, processor) pair placed with gap insertion (the baselines' rule);
reward only at the end: G = -Cmax/LB; advantage vs HEFT on the same instance, A = (Cmax_HEFT - Cmax)/LB.
REINFORCE with an entropy bonus; greedy decoding at evaluation. Data flow: training stream (`train` split,
indices >= 1000) -> gradients; `val` -> checkpoint selection and the fallback decision; test splits -> never here.
"""
from __future__ import annotations

import csv
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import torch

from .heuristics import HEURISTICS
from .model import Instance, ScheduleBuilder, bounds, upward_rank
from .workloads import generate

torch.set_num_threads(1)
torch.use_deterministic_algorithms(True)

FEATURES = ["log_cost_vs_best_proc", "cost_vs_task_mean", "task_size", "rank_u", "outdegree", "start_wait",
            "finish_vs_best_candidate", "idle_gap", "ready_offset", "fraction_placed", "ready_per_proc",
            "load_imbalance"]
HEFT_FEATURES = ("rank_u", "finish_vs_best_candidate")   # removed in the RL-NOHEFTFEAT ablation
INSERT = True                                              # decision 1 (approved): same placement rule as HEFT
SETTINGS = dict(lr=3e-4, batch=16, beta=0.01, clip=1.0, max_updates=3000, time_cap_s=2700.0, val_every=100,
                hidden=64, stream_seed=20261017, stream_offset=1000, bc_updates=200)   # predeclared; no tuning
CELLS = [(c, n, m) for c in ("regular", "irregular", "heterogeneous", "irregular_hetero")
         for n in (50, 100, 200) for m in (2, 4, 8)]       # the 36 in-distribution cells
CAMPAIGN_SEED = 20261011


class Context:
    """Per-instance constants for the features."""

    def __init__(self, inst: Instance):
        self.cost = inst.cost
        self.cbar = inst.cost.mean(axis=1)
        self.scale = float(self.cbar.mean())                 # mean task cost: the time unit of all features
        self.cmin = inst.cost.min(axis=1)
        rank = upward_rank(inst)
        self.rank = rank / rank.max()
        out = np.array([len(s) for s in inst.succs], dtype=float)
        self.outdeg = out / out.max() if out.max() > 0 else out
        self.n, self.m = inst.n, inst.m


def candidates(b: ScheduleBuilder, ctx: Context) -> tuple[list, np.ndarray]:
    """Every valid action (ready task in id order x processor in id order) and its 12 features."""
    pairs = [(t, p) for t in b.ready for p in range(ctx.m)]
    est = np.array([b.est(t, p, INSERT) for t, p in pairs])
    t_idx = np.array([t for t, _ in pairs])
    p_idx = np.array([p for _, p in pairs])
    c = ctx.cost[t_idx, p_idx]
    eft = est + c
    avail = np.array(b.avail)
    lo, s = avail.min(), ctx.scale
    X = np.column_stack([
        np.log(c / ctx.cmin[t_idx]),
        c / ctx.cbar[t_idx],
        ctx.cbar[t_idx] / s,
        ctx.rank[t_idx],
        ctx.outdeg[t_idx],
        (est - lo) / s,
        (eft - eft.min()) / s,
        (est - avail[p_idx]) / s,                            # < 0 when the task fills an idle gap
        (np.array(b.ready_time)[t_idx] - lo) / s,
        np.full(len(pairs), b._placed / ctx.n),
        np.full(len(pairs), len(b.ready) / ctx.m),
        np.full(len(pairs), (avail.max() - lo) / s),
    ])
    return pairs, X


def make_policy(n_features: int, hidden: int = SETTINGS["hidden"]) -> torch.nn.Module:
    return torch.nn.Sequential(torch.nn.Linear(n_features, hidden), torch.nn.ReLU(),
                               torch.nn.Linear(hidden, hidden), torch.nn.ReLU(), torch.nn.Linear(hidden, 1))


def rollout(inst: Instance, policy, cols, mode: str = "greedy", gen: torch.Generator | None = None,
            target: str | None = None):
    """Schedule one instance. mode: 'greedy' (argmax, ties -> first candidate = lowest task id, then processor),
    'sample' (multinomial with `gen`), or 'heft' (follow HEFT's choice; returns its log-probability, for BC).
    Returns (schedule, sum of log-probs, sum of entropies) — tensors are None in greedy mode."""
    b, ctx = ScheduleBuilder(inst), Context(inst)
    logps, ents = [], []
    rank = upward_rank(inst) if mode == "heft" else None
    while not b.done():
        pairs, X = candidates(b, ctx)
        x = torch.as_tensor(X[:, cols], dtype=torch.float32)
        if mode == "greedy":
            with torch.no_grad():
                k = int(torch.argmax(policy(x).squeeze(-1)))
        else:
            logits = policy(x).squeeze(-1)
            logp = torch.log_softmax(logits, dim=0)
            if mode == "sample":
                k = int(torch.multinomial(logp.exp(), 1, generator=gen))
            else:  # HEFT's decision: highest rank (ties lowest id), then earliest insertion finish (ties lowest p)
                t = min(b.ready, key=lambda t: (-rank[t], t))
                p = min(range(inst.m), key=lambda p: (b.eft(t, p, INSERT), p))
                k = pairs.index((t, p))
            logps.append(logp[k])
            ents.append(-(logp.exp() * logp).sum())
        b.place(*pairs[k], INSERT)
    s = b.schedule()
    if mode == "greedy":
        return s, None, None
    return s, torch.stack(logps).sum(), torch.stack(ents).sum()


def advantages(cmax, cmax_heft, lb) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Returns (G, raw A, standardised A). G = -Cmax/LB; A = G - b with b = -Cmax_HEFT/LB, so A > 0 exactly when the
    episode beat HEFT; standardised within the batch (zero mean, unit std; all-equal batch -> zeros)."""
    cmax, cmax_heft, lb = (np.asarray(v, dtype=float) for v in (cmax, cmax_heft, lb))
    G = -cmax / lb
    A = (cmax_heft - cmax) / lb
    sd = A.std()
    return G, A, (A - A.mean()) / sd if sd > 0 else np.zeros_like(A)


def stream_instance(k: int, settings: dict = SETTINGS) -> Instance:
    """k-th training instance: shared by all training seeds; `train` split, index >= stream_offset."""
    rng = np.random.default_rng(np.random.SeedSequence([settings["stream_seed"], k]))
    c, n, m = CELLS[int(rng.integers(len(CELLS)))]
    return generate(c, n, m, "train", settings["stream_offset"] + k, campaign_seed=CAMPAIGN_SEED)


def _heft_and_lb(inst: Instance) -> tuple[float, float]:
    return HEURISTICS["HEFT"](inst, None)[0].makespan, bounds(inst)["lower_bound"]


def validate_policy(policy, cols, val_insts, heft_c) -> float:
    """Mean rho = Cmax_RL / Cmax_HEFT over the validation instances, greedy decoding."""
    return float(np.mean([rollout(i, policy, cols)[0].makespan / h for i, h in zip(val_insts, heft_c)]))


def weights_id(policy) -> str:
    h = hashlib.sha256()
    for k, v in policy.state_dict().items():
        h.update(k.encode() + b"\0" + v.detach().numpy().tobytes())
    return h.hexdigest()[:16]


def train(seed: int, val_insts, forbidden_hashes: set, out_dir, ablation: bool = False, bc: bool = False,
          settings: dict | None = None, log=print, measured_extra=None) -> dict:
    """REINFORCE (optionally after the predeclared BC warm start). Keeps the checkpoint with the best val rho
    (strictly better; update 0 included). Writes the model directory once. Returns its model.json content."""
    st = {**SETTINGS, **(settings or {})}
    bad = {i.meta.get("split") for i in val_insts} - {"val"}
    if bad:
        raise ValueError(f"validation must use only 'val' instances, got {sorted(map(str, bad))}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True)                                   # never overwrite a model
    cols = [k for k, f in enumerate(FEATURES) if not (ablation and f in HEFT_FEATURES)]
    torch.manual_seed(seed)
    policy = make_policy(len(cols), st["hidden"])
    opt = torch.optim.Adam(policy.parameters(), lr=st["lr"])
    gen = torch.Generator().manual_seed(seed)
    val_heft = [_heft_and_lb(i)[0] for i in val_insts]
    t0, k, train_hashes, rows = time.perf_counter(), 0, [], []

    def next_batch():
        nonlocal k
        batch = []
        for _ in range(st["batch"]):
            inst = stream_instance(k, st)
            k += 1
            if inst.meta["hash"] in forbidden_hashes:
                raise RuntimeError(f"training instance {inst.id} collides with a held-out instance")
            train_hashes.append(inst.meta["hash"])
            batch.append(inst)
        return batch

    if bc:  # predeclared fallback: imitate HEFT's decisions first
        for _ in range(st["bc_updates"]):
            loss = torch.stack([-rollout(i, policy, cols, "heft")[1] for i in next_batch()]).mean()
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(policy.parameters(), st["clip"])
            opt.step()
    best = dict(rho=validate_policy(policy, cols, val_insts, val_heft), update=0,
                state={n: v.clone() for n, v in policy.state_dict().items()})
    rho0 = best["rho"]
    rows.append(dict(update=0, episodes=k, elapsed_s=time.perf_counter() - t0, mean_return="NA",
                     batch_mean_rho="NA", val_rho=rho0))
    log(f"update 0: val rho {rho0:.4f}")
    stop, update = "max_updates", 0
    for update in range(1, st["max_updates"] + 1):
        if time.perf_counter() - t0 >= st["time_cap_s"]:
            stop, update = "time_cap", update - 1
            break
        batch = next_batch()
        out = [rollout(i, policy, cols, "sample", gen) for i in batch]
        hl = [_heft_and_lb(i) for i in batch]
        G, _, A = advantages([o[0].makespan for o in out], [h for h, _ in hl], [lb for _, lb in hl])
        loss = (-(torch.stack([o[1] for o in out]) * torch.as_tensor(A, dtype=torch.float32)).sum()
                - st["beta"] * torch.stack([o[2] for o in out]).sum()) / len(batch)
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(policy.parameters(), st["clip"])
        opt.step()
        row = dict(update=update, episodes=k, elapsed_s=time.perf_counter() - t0, mean_return=float(G.mean()),
                   batch_mean_rho=float(np.mean([o[0].makespan / h for o, (h, _) in zip(out, hl)])), val_rho="NA")
        if update % st["val_every"] == 0:
            row["val_rho"] = validate_policy(policy, cols, val_insts, val_heft)
            if row["val_rho"] < best["rho"]:
                best = dict(rho=row["val_rho"], update=update,
                            state={n: v.clone() for n, v in policy.state_dict().items()})
            log(f"update {update}: val rho {row['val_rho']:.4f} (best {best['rho']:.4f} @ {best['update']}), "
                f"{row['elapsed_s']:.0f} s")
        rows.append(row)
    train_time = time.perf_counter() - t0
    extra = {k: (v() if callable(v) else v) for k, v in (measured_extra or {}).items()}
    policy.load_state_dict(best["state"])
    model_id = weights_id(policy)
    torch.save(dict(state_dict=policy.state_dict(), cols=cols, hidden=st["hidden"]), out_dir / "policy.pt")
    (out_dir / "train_hashes.txt").write_text("\n".join(train_hashes) + "\n")
    with open(out_dir / "training_log.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    meta = dict(model_id=model_id, seed=seed, ablation=ablation, features=[FEATURES[c] for c in cols],
                behaviour_cloning=bc, settings=st, insert=INSERT, updates_done=update, stop_reason=stop,
                episodes=k, best_update=best["update"], best_val_rho=best["rho"], val_rho_update0=rho0,
                learned_vs_update0=best["rho"] < rho0, val_instances=len(val_insts),
                measured=dict(train_time_s=train_time, **extra))   # measured values never enter model_id
    (out_dir / "model.json").write_text(json.dumps(meta, indent=2))
    for f in out_dir.iterdir():
        f.chmod(0o444)
    return meta


def load(model_dir) -> tuple[dict, str]:
    """Load a policy we saved; model_id is recomputed from the weights and must match model.json."""
    blob = torch.load(Path(model_dir) / "policy.pt", weights_only=True)
    policy = make_policy(len(blob["cols"]), blob["hidden"])
    policy.load_state_dict(blob["state_dict"])
    policy.eval()
    meta = json.loads((Path(model_dir) / "model.json").read_text())
    model_id = weights_id(policy)
    if model_id != meta["model_id"]:
        raise ValueError(f"weights in {model_dir} do not match model.json")
    train_hashes = set((Path(model_dir) / "train_hashes.txt").read_text().split())
    return dict(policy=policy, cols=blob["cols"], train_hashes=train_hashes, meta=meta), model_id


def schedule(inst: Instance, rng, model: dict):
    """Runner entry point: greedy decoding. Refuses instances the model was trained on."""
    if inst.meta.get("hash") in model["train_hashes"]:
        raise ValueError(f"instance {inst.id} is in the policy's training stream")
    t0 = time.perf_counter()
    s = rollout(inst, model["policy"], model["cols"])[0] if inst.n else ScheduleBuilder(inst).schedule()
    return s, dict(decision_time_s=time.perf_counter() - t0, decision_count=inst.n)

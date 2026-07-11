"""One policy, two evaluators, zero drift.

`carina compile` generates Rego for the cluster OPA; carina.authz enforces
the same semantics in-process. This suite evaluates both against identical
inputs and fails on any disagreement. Runs wherever the `opa` binary is on
PATH (CI installs it); skips silently elsewhere.
"""

import json
import shutil
import subprocess

import pytest

from carina import authz, compiler
from carina.contracts import Contract

from .conftest import CONTRACT_RAW

pytestmark = pytest.mark.skipif(
    shutil.which("opa") is None, reason="opa binary not on PATH")

OWNER = CONTRACT_RAW["owner"]


def _contract(classification="public", consumers=(), masks=()):
    raw = dict(CONTRACT_RAW)
    raw["classification"] = classification
    if consumers or masks:
        raw["access"] = {"consumers": list(consumers),
                         "masks": [dict(m) for m in masks]}
    return Contract(id="conf-test", path=None, raw=raw, product_id="p")


ACTORS = [
    authz.Actor.anonymous(),
    authz.Actor("authenticated-outsider", groups=["somewhere@else"], authenticated=True),
    authz.Actor("owner-member", groups=[OWNER], authenticated=True),
    authz.Actor("consumer", groups=["analysts@carina.local"], authenticated=True),
]

CONTRACTS = [
    _contract("public"),
    _contract("internal"),
    _contract("internal", consumers=["analysts@carina.local"]),
    _contract("confidential", masks=[{"column": "value", "treatment": "hash"}]),
]


def _opa_eval(rego: str, query: str, opa_input: dict, tmp_path) -> object:
    policy = tmp_path / "policy.rego"
    policy.write_text(rego)
    infile = tmp_path / "input.json"
    infile.write_text(json.dumps(opa_input))
    out = subprocess.run(
        ["opa", "eval", "--format", "json", "--data", str(policy),
         "--input", str(infile), query],
        capture_output=True, text=True, check=True)
    results = json.loads(out.stdout)["result"]
    return results[0]["expressions"][0]["value"] if results else None


@pytest.mark.parametrize("action", ["read", "write"])
def test_allow_matches_between_python_and_opa(tmp_path, action):
    disagreements = []
    for ct in CONTRACTS:
        rego = compiler.compile_policy_rego(ct)
        pkg = "carina.contracts.conf_test"
        for actor in ACTORS:
            py = authz.decide(ct, actor, action).allow
            opa = bool(_opa_eval(rego, f"data.{pkg}.allow",
                                 authz.opa_input(ct, actor, action), tmp_path))
            if py != opa:
                disagreements.append(
                    f"{ct.classification}/{actor.subject}/{action}: python={py} opa={opa}")
    assert not disagreements, "policy evaluators disagree:\n" + "\n".join(disagreements)


def test_masks_match_between_python_and_opa(tmp_path):
    ct = _contract("confidential", masks=[{"column": "value", "treatment": "hash"}])
    rego = compiler.compile_policy_rego(ct)
    pkg = "carina.contracts.conf_test"
    for actor in ACTORS:
        py = authz.masks_for(ct, actor)
        opa = _opa_eval(rego, f"data.{pkg}.mask",
                        authz.opa_input(ct, actor, "read"), tmp_path) or []
        assert sorted(m["column"] for m in py) == sorted(m["column"] for m in opa), \
            f"mask mismatch for {actor.subject}"


def test_generated_rego_compiles_cleanly(tmp_path):
    for ct in CONTRACTS:
        policy = tmp_path / "check.rego"
        policy.write_text(compiler.compile_policy_rego(ct))
        subprocess.run(["opa", "check", str(policy)], capture_output=True,
                       text=True, check=True)

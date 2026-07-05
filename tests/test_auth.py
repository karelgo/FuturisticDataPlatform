"""OIDC verification: real RS256 tokens against a fake issuer's JWKS."""

import pytest

from carina import auth

from .conftest import AUDIENCE, ISSUER


def _verifier(fake_issuer):
    return auth.OIDCVerifier(ISSUER, AUDIENCE, transport=fake_issuer.transport())


def test_valid_token_yields_actor(fake_issuer):
    v = _verifier(fake_issuer)
    actor = v.verify(fake_issuer.mint("alice", groups=["analysts@carina.local"]))
    assert actor.subject == "alice"
    assert actor.groups == ["analysts@carina.local"]
    assert actor.authenticated is True
    assert actor.kind == "human"


def test_agent_kind_claim(fake_issuer):
    v = _verifier(fake_issuer)
    actor = v.verify(fake_issuer.mint("analyst-agent", kind="agent"))
    assert actor.kind == "agent"


@pytest.mark.parametrize("kwargs,fragment", [
    ({"expired": True}, "Expired"),
    ({"audience": "someone-else"}, "Audience"),
    ({"issuer": "https://evil.example/realms/x"}, "Issuer"),
])
def test_bad_tokens_rejected(fake_issuer, kwargs, fragment):
    v = _verifier(fake_issuer)
    with pytest.raises(auth.AuthError) as e:
        v.verify(fake_issuer.mint("mallory", **kwargs))
    assert fragment.lower() in str(e.value).lower()


def test_unknown_kid_rejected_after_refresh(fake_issuer):
    v = _verifier(fake_issuer)
    with pytest.raises(auth.AuthError, match="no JWKS key"):
        v.verify(fake_issuer.mint("mallory", kid="rogue-key"))


def test_wrong_signature_rejected(fake_issuer):
    from .conftest import FakeIssuer
    rogue = FakeIssuer()  # different keypair, same kid
    v = _verifier(fake_issuer)
    with pytest.raises(auth.AuthError):
        v.verify(rogue.mint("mallory"))


def test_mode_none_yields_dev_actor(monkeypatch):
    monkeypatch.delenv("CARINA_AUTH_MODE", raising=False)
    actor = auth.actor_from_authorization(None)
    assert actor.subject == "dev@local"
    assert actor.authenticated is True


def test_mode_oidc_requires_bearer(monkeypatch):
    monkeypatch.setenv("CARINA_AUTH_MODE", "oidc")
    monkeypatch.setenv("CARINA_OIDC_ISSUER", ISSUER)
    auth.reset()
    with pytest.raises(auth.AuthError, match="missing Bearer"):
        auth.actor_from_authorization(None)
    auth.reset()

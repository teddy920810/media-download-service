from importlib import metadata
import hashlib
from pathlib import Path
import ssl
import tomllib

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version
import pytest


ROOT = Path(__file__).resolve().parents[1]
CERTIFI_FIXED_VERSION = Version("2026.10.19")
# emSign ECC Root CA - G3, removed in upstream commit 5cb238caeeb6c30e.
COMPROMISED_ROOT_SHA256 = "86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b"


def locked_requirements():
    requirements = {}
    for line in (ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        requirement = Requirement(line)
        if requirement.marker is None or requirement.marker.evaluate():
            requirements[canonicalize_name(requirement.name)] = requirement
    return requirements


def project_dependencies():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return [Requirement(value) for value in project["project"]["dependencies"]]


@pytest.mark.parametrize(
    ("name", "fixed", "vulnerable"),
    [("certifi", "2026.10.19", "2026.7.22"), ("urllib3", "2.8.0", "2.7.0")],
)
def test_security_floors_are_explicit_and_locked(name, fixed, vulnerable):
    declared = {canonicalize_name(req.name): req for req in project_dependencies()}
    assert name in declared, "Keep security floors even outside a locked install."
    assert Version(fixed) in declared[name].specifier
    assert Version(vulnerable) not in declared[name].specifier
    pin = str(locked_requirements()[name].specifier)
    assert pin.startswith("==") and "*" not in pin
    assert Version(pin[2:]) >= Version(fixed)


def test_container_installs_locked_dependencies_before_the_project():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY requirements.lock" in dockerfile
    assert "python -m pip install --no-cache-dir -r requirements.lock" in dockerfile
    assert "python -m pip install --no-cache-dir --no-deps ." in dockerfile
    assert "python -m pip check" in dockerfile
    assert dockerfile.index("-r requirements.lock") < dockerfile.index("--no-deps .")


def test_ci_and_documented_setup_use_the_runtime_constraints():
    for filename in (".github/workflows/ci.yml", "README.md"):
        content = (ROOT / filename).read_text(encoding="utf-8")
        assert 'python -m pip install -c requirements.lock -e ".[dev]"' in content
        assert "python -m pip check" in content


def test_locked_runtime_dependency_closure_matches_installed_metadata():
    """Catch missing transitive/extra dependencies rather than silently resolving them."""
    locked = locked_requirements()
    pending = project_dependencies()
    checked = set()
    while pending:
        requirement = pending.pop()
        name = canonicalize_name(requirement.name)
        installed = Version(metadata.version(name))
        assert name in locked, f"{name} is a runtime dependency missing from requirements.lock"
        assert installed in locked[name].specifier, f"{name} differs from the runtime lock"
        assert installed in requirement.specifier, f"{name} does not satisfy {requirement}"
        key = (name, frozenset(requirement.extras))
        if key in checked:
            continue
        checked.add(key)
        for value in metadata.requires(name) or []:
            dependency = Requirement(value)
            contexts = {"", *requirement.extras}
            if dependency.marker is None or any(
                dependency.marker.evaluate({"extra": extra}) for extra in contexts
            ):
                pending.append(dependency)


def test_installed_certifi_excludes_the_compromised_root():
    import certifi

    assert Version(metadata.version("certifi")) >= CERTIFI_FIXED_VERSION
    context = ssl.create_default_context(cafile=certifi.where())
    certificates = context.get_ca_certs(binary_form=True)
    assert len(certificates) > 100, "The replacement bundle must remain usable."
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    fingerprints = {hashlib.sha256(certificate).hexdigest() for certificate in certificates}
    assert COMPROMISED_ROOT_SHA256 not in fingerprints


def test_requests_and_botocore_use_the_patched_bundle_by_default():
    import botocore.httpsession
    import certifi
    import requests.certs

    assert Path(requests.certs.where()).samefile(certifi.where())
    assert Path(botocore.httpsession.get_cert_path(True)).samefile(certifi.where())

"""
ACE dependency version-pin tests — BLOCKER-5 acceptance gate.

Validates that installed package versions meet the minimum floors that patch
the CVEs identified in the pre-traffic audit:
  CVE-2024-24762  fastapi>=0.109.1   (multipart DoS on /intake/submit)
  CVE-2024-3772   pydantic>=2.7.0    (ReDoS via EmailStr on IntakePayload)
  CVE-2026-32597  PyJWT>=2.12.0      (crit header bypass on x402 CDP auth path)
  CVE-2026-42561  python-multipart>=0.0.27  (new multipart DoS)
  GHSA-9h52-p55h-vw2f  mcp>=1.23.0  (DNS rebinding; highest MCP floor required)
"""
from importlib.metadata import version
from packaging.version import Version
import pytest


REQUIRED_FLOORS = {
    "fastapi": "0.109.1",
    "pydantic": "2.7.0",
    "PyJWT": "2.12.0",
    "python-multipart": "0.0.27",
    "mcp": "1.23.0",
}


@pytest.mark.parametrize("package,floor", REQUIRED_FLOORS.items())
def test_package_meets_cve_floor(package, floor):
    installed = version(package)
    assert Version(installed) >= Version(floor), (
        f"{package} {installed} is below CVE-patched floor {floor}"
    )

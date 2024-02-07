"""Test Aeromancy is importable."""

import aeromancy


def test_import_aeromancy() -> None:
    """Ensure aeromancy package can be imported."""
    print("Contents:", dir(aeromancy))

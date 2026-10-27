"""Immutable historical test inputs, never current allocation authority.

The ledger last changed at218751113aa875534be4f0f2e43040d1282af9e3;
all bytes below are retained from f4efa458f24ce3703519615df76c29b6b2b4e3ea.
Only explicitly scoped historical tests select these inputs. Importing this
module does not change any production default or enable a reservation.
"""
import hashlib
from pathlib import Path
import tempfile

from lyra_source_snapshots import read_snapshot


REVISION = 'f4efa458f24ce3703519615df76c29b6b2b4e3ea'
FIXTURES = Path(__file__).resolve().parent / 'fixtures/lyra_historical_reservation'
LEDGER_SHA256 = 'e08c872e206f7c8068a3aeb47ebd9c5fcb32acb54b07aa27c13affc668e06503'
SOURCE_SHA256 = {
    'Items/ice_rod.asm': '8bcd1f79e44e182728726c49bccd99ff2067d56d63df6552376d1244abd87cd5',
    'Dungeons/Collision/GlobalCollisionTables.asm': '37b472419b5095eff2241b6792be43d3257252b0b645f3d72645189365658c8e',
    'Core/patches.asm': '66101c3b4a4a027c4fa13fbb121bc469c28809dc3f2414969935626c7d3e4619',
    'Data/dungeons/custom_collision.json': '13342cd4fc8f719e6c502ada53225dd55df8dcd73f299db02fd42b1288c85514',
}


def _root(owner):
    temporary = tempfile.TemporaryDirectory()
    cleanup = owner.addClassCleanup if isinstance(owner, type) else owner.addCleanup
    cleanup(temporary.cleanup)
    return Path(temporary.name).resolve()


def historical_ledger_path(owner):
    raw = (FIXTURES / 'Config/allocation_ownership.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != LEDGER_SHA256:
        raise AssertionError('Historical test ledger snapshot changed')
    path = _root(owner) / 'allocation_ownership.json'
    path.write_bytes(raw)
    path.chmod(0o444)
    return path


def historical_source_root(owner):
    """Materialize only the four exact source inputs for opt-in private tests."""
    root = _root(owner)
    for name, digest in SOURCE_SHA256.items():
        raw = read_snapshot(REVISION, name)
        if hashlib.sha256(raw).hexdigest() != digest:
            raise AssertionError('Historical test source snapshot changed: ' + name)
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        path.chmod(0o444)
    return root

import pytest

from app import seed
from app.db import connect


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Fresh sqlite DB under an isolated DATA_DIR, returns a connection."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    seed.init_db()
    c = connect()
    yield c
    c.close()


def set_lock(c, wish_id, claimer, claimed_at, expires_at):
    c.execute(
        "UPDATE wishes SET status='claimed', claimer=?, claimed_at=?, expires_at=?"
        " WHERE id=?",
        (claimer, claimed_at, expires_at, wish_id),
    )
    c.commit()

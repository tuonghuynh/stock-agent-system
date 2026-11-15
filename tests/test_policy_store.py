from copy import deepcopy

import pytest
import sqlalchemy as sa

from stock_agent.database import Base
from stock_agent.policy import PolicyDocument, PolicyVersionStore, load_policy


def test_at001_policy_version_persists_idempotently_and_is_immutable() -> None:
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    policy = load_policy("POLICY_V1.yaml")
    store = PolicyVersionStore()
    with engine.begin() as connection:
        first = store.persist_immutable(connection, policy)
        duplicate = store.persist_immutable(connection, policy)
        assert duplicate == first
        assert len(first.content_hash) == 64

        changed = deepcopy(policy.model_dump(mode="python"))
        changed["decision"]["minimum_executable_confidence"] = 66
        with pytest.raises(ValueError, match="immutable"):
            store.persist_immutable(connection, PolicyDocument.model_validate(changed))

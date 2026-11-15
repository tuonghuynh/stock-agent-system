"""Provider interface and deterministic test provider."""

from collections.abc import Iterable
from threading import RLock
from typing import Protocol

from stock_agent.model_gateway.models import ModelCall, ModelResponse


class ModelProvider(Protocol):
    def complete(self, call: ModelCall) -> ModelResponse: ...


class FakeModelProvider:
    """Returns a bounded scripted sequence without network or secret access."""

    def __init__(self, responses: Iterable[ModelResponse]) -> None:
        self._responses = iter(responses)
        self._calls: list[ModelCall] = []
        self._lock = RLock()

    def complete(self, call: ModelCall) -> ModelResponse:
        with self._lock:
            self._calls.append(call)
            try:
                return next(self._responses)
            except StopIteration as error:
                raise RuntimeError("fake model response sequence exhausted") from error

    @property
    def calls(self) -> tuple[ModelCall, ...]:
        with self._lock:
            return tuple(self._calls)


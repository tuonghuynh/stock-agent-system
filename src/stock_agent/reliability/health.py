"""Liveness/readiness and required dependency degradation."""

from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True, slots=True)
class DependencyState:
    name: str
    healthy: bool
    required: bool = True
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("dependency name must not be blank")


class OperationalHealth:
    """Process liveness is independent; readiness requires critical dependencies."""

    def __init__(self) -> None:
        self._states: dict[str, DependencyState] = {}
        self._lock = RLock()

    def record(self, state: DependencyState) -> None:
        with self._lock:
            self._states[state.name] = state

    @property
    def live(self) -> bool:
        return True

    @property
    def ready(self) -> bool:
        with self._lock:
            return bool(self._states) and all(
                state.healthy for state in self._states.values() if state.required
            )

    def failed_required(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(
                sorted(
                    state.name
                    for state in self._states.values()
                    if state.required and not state.healthy
                )
            )

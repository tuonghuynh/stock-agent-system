"""Local recommendation-to-fill demonstration using only deterministic fakes.

Run from the repository root with::

    PYTHONPATH=src .venv/bin/python -m stock_agent.application.demo

No network, credentials, approval prompt, or live brokerage endpoint is used.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict

from stock_agent.agents.critic import CriticInput, CriticResult, DeterministicCritic
from stock_agent.agents.critic.models import CritiqueDisposition as ReviewDisposition
from stock_agent.agents.portfolio import (
    CriticDisposition,
    CritiqueInput,
    PortfolioDraft,
    PortfolioSynthesisInput,
    PortfolioSynthesisResult,
    PortfolioSynthesizer,
)
from stock_agent.agents.research import (
    ResearchAgent,
    ResearchRequest,
    ResearchResult,
    ResearchStatus,
)
from stock_agent.agents.research.models import ResearchDimension, ResearchGatewayCall
from stock_agent.coordinator import (
    BudgetUsage,
    Coordinator,
    InMemoryRunStore,
    RunOutcome,
    StepResult,
)
from stock_agent.coordinator import (
    CriticDisposition as CoordinatorCriticDisposition,
)
from stock_agent.domain.models import (
    EvidenceSnapshot,
    FindingClassification,
    IntentStatus,
    OrderType,
    RecommendationAction,
    RunManifest,
    RunStatus,
    TimeInForce,
    TradeEnvironment,
    TradeIntent,
    TradeSide,
    TrustClass,
)
from stock_agent.evidence import EvidenceMaterial, EvidenceSnapshotBuilder
from stock_agent.execution.broker import BrokerOrder, BrokerOrderStatus
from stock_agent.execution.fake_broker import FakeBroker
from stock_agent.execution.identity import derive_idempotency_key
from stock_agent.execution.reconciliation import (
    ExecutionPause,
    ExecutionReconciler,
    Fill,
    FillLedger,
)
from stock_agent.execution.service import ExecutionService
from stock_agent.execution.store import InMemoryExecutionStore
from stock_agent.policy.loader import load_policy
from stock_agent.risk.authorization import AuthorizationOutcome, RiskAuthorizationService
from stock_agent.risk.engine import DeterministicRiskEngine
from stock_agent.risk.freshness import RiskDataTimestamps
from stock_agent.risk.models import AssetType, OrderSide, RiskContext
from stock_agent.risk.pause import PauseController
from stock_agent.risk.reservations import (
    InMemoryReservationStore,
    ReservationCapacity,
    ReservationRequest,
)

_NAMESPACE = UUID("f28d382d-d77e-429b-bccd-7e9a16b7ab3b")
_NOW = datetime(2026, 11, 14, 20, tzinfo=UTC)
_RUN_ID = uuid5(_NAMESPACE, "fake-paper-demo-run")
_EVIDENCE_ID = uuid5(_NAMESPACE, "fake-paper-demo-evidence")


class DemoResult(BaseModel):
    """Observable evidence returned by the local manual demonstration."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    trace_id: str
    outcome: RunOutcome
    recommendation_action: RecommendationAction
    risk_approved: bool
    risk_failures: tuple[str, ...]
    intent_id: UUID | None = None
    intent_status: IntentStatus | None = None
    broker_order_id: str | None = None
    filled_quantity: Decimal = Decimal(0)
    broker_submission_count: int = 0
    human_approval_requested: bool = False
    environment: TradeEnvironment = TradeEnvironment.PAPER


class _DeterministicResearchGateway:
    def research(self, call: ResearchGatewayCall) -> object:
        return {
            "symbol": call.symbol,
            "horizon": call.horizon,
            "findings": tuple(
                {
                    "dimension": dimension,
                    "claim": f"Evidence-backed {dimension.value.lower()} observation",
                    "classification": (
                        FindingClassification.FACT
                        if dimension is ResearchDimension.FUNDAMENTALS
                        else FindingClassification.DERIVATION
                    ),
                    "evidence_ids": (_EVIDENCE_ID,),
                    "supporting_evidence": (_EVIDENCE_ID,),
                    "contradicting_evidence": (),
                    "confidence": 80,
                    "assumptions": (),
                    "missing_information": (),
                    "analysis_timestamp": call.as_of,
                }
                for dimension in ResearchDimension
            ),
        }


class _DemoWorkflowPorts:
    def __init__(self, *, policy_path: Path, symbol_allowed: bool) -> None:
        self.policy = load_policy(policy_path)
        self.symbol_allowed = symbol_allowed
        self.snapshot: EvidenceSnapshot | None = None
        self.research_result: ResearchResult | None = None
        self.portfolio_result: PortfolioSynthesisResult | None = None
        self.critique: CriticResult | None = None
        self.risk_outcome: AuthorizationOutcome | None = None
        self.intent: TradeIntent | None = None
        self.final_status: IntentStatus | None = None
        self.order: BrokerOrder | None = None
        self.filled_quantity = Decimal(0)
        self.broker = FakeBroker(lambda: _NOW)
        self.execution_store = InMemoryExecutionStore()

    def evidence(self, manifest: RunManifest) -> StepResult:
        self.snapshot = EvidenceSnapshotBuilder().build(
            snapshot_id=manifest.data_snapshot_id,
            run_id=manifest.run_id,
            as_of=manifest.as_of,
            materials=(
                EvidenceMaterial(
                    evidence_id=_EVIDENCE_ID,
                    type="FILING_AND_MARKET_DATA",
                    content_reference="immutable://demo/aapl/point-in-time",
                    source_id="demo-primary",
                    source_uri=None,
                    publisher="Deterministic Demo",
                    source_timestamp=manifest.as_of - timedelta(minutes=2),
                    retrieved_at=manifest.as_of - timedelta(minutes=1),
                    content_hash="a" * 64,
                    trust_class=TrustClass.PRIMARY,
                    maximum_age=timedelta(days=1),
                ),
            ),
        )
        return StepResult(reference=f"snapshot:{self.snapshot.snapshot_id}", usage=BudgetUsage())

    def research(self, manifest: RunManifest, evidence: StepResult) -> StepResult:
        assert self.snapshot is not None
        self.research_result = ResearchAgent(_DeterministicResearchGateway()).run(
            ResearchRequest(
                run_id=manifest.run_id,
                objective=manifest.objective,
                symbol=manifest.symbols[0],
                horizon=manifest.horizon,
                snapshot=self.snapshot,
                model_version="deterministic-demo-1",
                prompt_version="research-demo-1",
            )
        )
        if self.research_result.status is not ResearchStatus.VALIDATED:
            return StepResult(reference="research:wait", outcome=RunOutcome.WAIT)
        return StepResult(
            reference="research:validated",
            usage=BudgetUsage(model_calls=1, tokens=100, cost=Decimal("0.01")),
        )

    def portfolio(
        self, manifest: RunManifest, research: StepResult, critique: StepResult | None
    ) -> StepResult:
        assert self.snapshot is not None and self.research_result is not None
        disposition = CriticDisposition.APPROVED
        objections: tuple[str, ...] = ()
        conflicts: tuple[str, ...] = ()
        if self.critique is not None and self.critique.blocks_intent:
            disposition = CriticDisposition.NEEDS_REVIEW
            objections = tuple(item.summary for item in self.critique.objections)
            conflicts = self.critique.unresolved_material_conflicts
        synthesis = PortfolioSynthesisInput(
            run_id=manifest.run_id,
            symbol=manifest.symbols[0],
            horizon=manifest.horizon,
            as_of=manifest.as_of,
            next_market_close=manifest.as_of + timedelta(hours=4),
            snapshot_id=self.snapshot.snapshot_id,
            snapshot_hash=self.snapshot.content_hash,
            evidence_ids=tuple(entry.evidence_id for entry in self.snapshot.entries),
            policy_version=manifest.policy_version,
            release_version=manifest.release_version,
            workflow_version=manifest.workflow_version,
            model_version="deterministic-demo-1",
            prompt_version="portfolio-demo-1",
            current_weight=Decimal(2),
            maximum_target_weight=Decimal(10),
            material_data_complete=True,
            research_findings=self.research_result.findings,
            critique=CritiqueInput(
                disposition=disposition,
                objections=objections,
                unresolved_material_conflicts=conflicts,
                evidence_ids=(_EVIDENCE_ID,),
            ),
            draft=PortfolioDraft(
                symbol=manifest.symbols[0],
                horizon=manifest.horizon,
                action=RecommendationAction.BUY,
                thesis="Deterministic evidence supports a staged paper position",
                bull_case="Fundamentals and trend remain supportive",
                base_case="Current evidence persists",
                bear_case="Growth or trend weakens",
                supporting_evidence_ids=(_EVIDENCE_ID,),
                contradicting_evidence_ids=(),
                material_conflicts=(),
                invalidation_conditions=("Revenue growth turns negative",),
                confidence=80,
                target_weight=Decimal(4),
                entry_conditions=("All deterministic risk checks pass",),
                exit_conditions=("The thesis invalidates",),
            ),
        )
        self.portfolio_result = PortfolioSynthesizer().synthesize(synthesis)
        outcome = (
            RunOutcome.RUNNING
            if self.portfolio_result.recommendation.action is RecommendationAction.BUY
            else RunOutcome.NEEDS_REVIEW
        )
        return StepResult(
            reference=f"recommendation:{self.portfolio_result.recommendation.recommendation_id}",
            outcome=outcome,
            usage=BudgetUsage(model_calls=1, tokens=100, cost=Decimal("0.01")),
        )

    def critic(self, manifest: RunManifest, candidate: StepResult) -> StepResult:
        assert self.portfolio_result is not None and self.research_result is not None
        self.critique = DeterministicCritic().review(
            CriticInput(
                run_id=manifest.run_id,
                objective=manifest.objective,
                symbol=manifest.symbols[0],
                horizon=manifest.horizon,
                as_of=manifest.as_of,
                candidate=self.portfolio_result.recommendation,
                findings=self.research_result.findings,
                available_evidence_ids=frozenset({_EVIDENCE_ID}),
                maximum_target_weight=Decimal(10),
                maximum_objections=10,
            )
        )
        mapped = {
            ReviewDisposition.CLEAR: CoordinatorCriticDisposition.CLEAR,
            ReviewDisposition.REVISE: CoordinatorCriticDisposition.REVISE,
            ReviewDisposition.WAIT: CoordinatorCriticDisposition.WAIT,
            ReviewDisposition.NEEDS_REVIEW: CoordinatorCriticDisposition.NEEDS_REVIEW,
        }[self.critique.disposition]
        return StepResult(
            reference="critic:complete",
            critic_disposition=mapped,
            usage=BudgetUsage(model_calls=1, tokens=50, cost=Decimal("0.005")),
        )

    def risk(self, manifest: RunManifest, candidate: StepResult) -> StepResult:
        assert self.portfolio_result is not None
        recommendation = self.portfolio_result.recommendation
        risk_context = RiskContext(
            recommendation_id=recommendation.recommendation_id,
            account_snapshot_id=uuid5(_NAMESPACE, "demo-account-snapshot"),
            evaluated_at=manifest.as_of,
            evidence_timestamp=manifest.as_of - timedelta(seconds=5),
            policy=self.policy,
            symbol=recommendation.symbol,
            asset_type=AssetType.STOCK,
            sector="TECHNOLOGY",
            side=OrderSide.BUY,
            asset_tradable=True,
            regular_session_open=True,
            allowed_symbols=(
                frozenset({recommendation.symbol}) if self.symbol_allowed else frozenset()
            ),
            current_weight_pct=recommendation.current_weight,
            proposed_target_weight_pct=recommendation.target_weight,
            current_sector_weight_pct=Decimal(20),
            proposed_sector_weight_pct=Decimal(22),
            cash_pct_after_order=Decimal(20),
            new_exposure_today_pct_after_order=Decimal(2),
            new_positions_today_after_order=1,
            weekly_turnover_pct_after_order=Decimal(2),
            trading_days_until_earnings=10,
        )
        timestamp = manifest.as_of - timedelta(seconds=5)
        self.risk_outcome = RiskAuthorizationService(
            DeterministicRiskEngine(),
            InMemoryReservationStore(),
            PauseController(self.policy.pause),
        ).authorize(
            risk_context,
            timestamps=RiskDataTimestamps(
                quote=timestamp,
                position=timestamp,
                pending_orders=timestamp,
                account=timestamp,
                buying_power=timestamp,
            ),
            request=ReservationRequest(
                reservation_id=uuid5(_NAMESPACE, "demo-reservation"),
                intent_id=uuid5(_NAMESPACE, "demo-intent"),
                symbol=recommendation.symbol,
                side=OrderSide.BUY,
                quantity=Decimal(2),
                cash_required=Decimal(300),
                created_at=manifest.as_of,
            ),
            capacity=ReservationCapacity(settled_cash=Decimal(10_000), positions={}),
        )
        return StepResult(
            reference="risk:approved" if self.risk_outcome.approved else "risk:rejected",
            risk_approved=self.risk_outcome.approved,
        )

    def execute(self, manifest: RunManifest, candidate: StepResult) -> StepResult:
        assert self.portfolio_result is not None and self.risk_outcome is not None
        if not self.risk_outcome.approved:
            raise PermissionError("execution cannot run without deterministic risk approval")
        recommendation = self.portfolio_result.recommendation
        intent_id = uuid5(_NAMESPACE, "demo-intent")
        risk_decision_id = uuid5(_NAMESPACE, "demo-risk-decision")
        limit_price = Decimal(150)
        quantity = Decimal(2)
        self.intent = TradeIntent(
            intent_id=intent_id,
            idempotency_key=derive_idempotency_key(
                recommendation_id=recommendation.recommendation_id,
                policy_version=manifest.policy_version,
                account_id_hash="demo-account-hash",
                symbol=recommendation.symbol,
                side=TradeSide.BUY,
                target_delta=quantity,
                order_type=OrderType.LIMIT,
                limit_price=limit_price,
                time_in_force=TimeInForce.DAY,
                expires_at=recommendation.expires_at,
            ),
            recommendation_id=recommendation.recommendation_id,
            risk_decision_id=risk_decision_id,
            environment=TradeEnvironment.PAPER,
            symbol=recommendation.symbol,
            side=TradeSide.BUY,
            quantity=quantity,
            order_type=OrderType.LIMIT,
            limit_price=limit_price,
            time_in_force=TimeInForce.DAY,
            expires_at=recommendation.expires_at,
            policy_version=manifest.policy_version,
            created_at=manifest.as_of,
            status=IntentStatus.RESERVED,
        )
        submitted = ExecutionService(self.execution_store, self.broker, lambda: _NOW).submit(
            self.intent
        )
        assert submitted.order is not None
        self.order = submitted.order
        fill = Fill(
            broker_fill_id="demo-fill-1",
            broker_order_id=self.order.broker_order_id,
            quantity=quantity,
            price=limit_price,
            executed_at=_NOW,
        )
        balance = FillLedger(quantity).apply(fill)
        filled_order = BrokerOrder(
            broker_order_id=self.order.broker_order_id,
            client_order_id=self.order.client_order_id,
            status=BrokerOrderStatus.FILLED,
            requested_quantity=quantity,
            filled_quantity=quantity,
            average_fill_price=limit_price,
            submitted_at=self.order.submitted_at,
            updated_at=_NOW,
        )
        final = ExecutionReconciler(
            self.execution_store, self.broker, ExecutionPause()
        ).apply_order(submitted, filled_order)
        self.final_status = final.intent.status
        self.filled_quantity = balance.filled_quantity
        return StepResult(reference=f"fill:{fill.broker_fill_id}", outcome=RunOutcome.ACCEPTED)


def run_fake_paper_demo(
    *, policy_path: Path = Path("POLICY_V1.yaml"), symbol_allowed: bool = True
) -> DemoResult:
    """Run an accepted or risk-rejected lifecycle without human approval."""
    trace_id = "trace-fake-paper-demo"
    manifest = RunManifest(
        run_id=_RUN_ID,
        trace_id=trace_id,
        objective="Evaluate AAPL for a bounded paper position",
        symbols=("AAPL",),
        horizon="20 trading days",
        as_of=_NOW,
        policy_version="1",
        release_version="release-1",
        workflow_version="workflow-1",
        data_snapshot_id=uuid5(_NAMESPACE, "demo-snapshot"),
        model_versions={"research": "deterministic-demo-1"},
        prompt_versions={"research": "research-demo-1", "portfolio": "portfolio-demo-1"},
        tool_versions={"evidence": "readonly-1"},
        deadline=_NOW + timedelta(minutes=5),
        max_model_calls=4,
        max_tool_calls=4,
        max_tokens=1000,
        max_cost=Decimal(1),
        allowed_actions=("READ_EVIDENCE", "PROPOSE_PAPER_POSITION"),
        prohibited_actions=("LIVE_TRADING", "BROKER_ACCESS", "POLICY_MUTATION"),
        status=RunStatus.CREATED,
    )
    ports = _DemoWorkflowPorts(policy_path=policy_path, symbol_allowed=symbol_allowed)
    workflow = Coordinator(InMemoryRunStore(), ports, lambda: _NOW).run(manifest)
    recommendation_action = (
        ports.portfolio_result.recommendation.action
        if ports.portfolio_result is not None
        else RecommendationAction.WAIT
    )
    risk_failures = (
        tuple(check.rule_id for check in ports.risk_outcome.checks if not check.passed)
        if ports.risk_outcome is not None
        else ()
    )
    return DemoResult(
        trace_id=trace_id,
        outcome=workflow.outcome,
        recommendation_action=recommendation_action,
        risk_approved=bool(ports.risk_outcome and ports.risk_outcome.approved),
        risk_failures=risk_failures,
        intent_id=ports.intent.intent_id if ports.intent else None,
        intent_status=ports.final_status,
        broker_order_id=ports.order.broker_order_id if ports.order else None,
        filled_quantity=ports.filled_quantity,
        broker_submission_count=ports.broker.submission_count,
    )


if __name__ == "__main__":
    print(run_fake_paper_demo().model_dump_json(indent=2))

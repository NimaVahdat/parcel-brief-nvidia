"""The vote-predictor agent: orchestrate the panel, aggregate, and trace the reasoning.

Given an application and the committee, the agent retrieves precedent, runs the multi-agent
panel (per-councillor Reasoner + deterministic Skeptic; see ``panel.py``), aggregates the
surviving per-councillor probabilities into a committee approval probability with the exact
Poisson-binomial (the Clerk, in ``aggregate.py``), and computes counterfactual levers.

It exposes the result two ways: ``predict`` returns the frozen Contract-1 ``VotePrediction``;
``predict_with_trace`` additionally returns the ``AgentTrace`` (per-councillor reasoning and
Skeptic verdicts) that the service surfaces as an additive field and the UI drills into.

When no model server is reachable the panel degrades to a transparent record+staff heuristic,
so the contract never hard-fails.
"""

from __future__ import annotations

from vote_predictor import config, panel, retrieval
from vote_predictor.aggregate import poisson_binomial_majority, swing_councillors
from vote_predictor.schemas import AgentTrace, Lever, VotePrediction


class VotePredictorAgent:
    """Predicts council votes by running the grounded multi-agent panel.

    Attributes:
        profiles (dict[str, dict]): Per-councillor voting profiles for grounding.
        use_llm (bool): Whether to attempt the LLM Reasoner before the heuristic.
    """

    def __init__(
        self, profiles: dict[str, dict] | None = None, use_llm: bool | None = None
    ) -> None:
        """Initialize the agent with councillor profiles and an LLM toggle.

        Args:
            profiles (dict[str, dict] | None): Councillor profiles; loaded/built if None.
            use_llm (bool | None): Force the LLM on/off; defaults to ``config.USE_LLM``.
        """
        self.profiles = profiles if profiles is not None else retrieval.load_or_build_profiles()
        self.use_llm = config.USE_LLM if use_llm is None else use_llm

    def _levers(
        self,
        application: dict,
        councillors: list[str],
        staff_signal: float,
        ward: str | None,
        base: float,
    ) -> list[Lever]:
        """Compute counterfactual levers by perturbing features and re-scoring deterministically.

        Uses the transparent heuristic scorer (not a fresh LLM panel) so levers are fast and
        consistent — each lever is the change in committee approval probability from one edit.

        Args:
            application (dict): The original application fields.
            councillors (list[str]): Normalized councillor ids.
            staff_signal (float): Staff recommendation signal.
            ward (str | None): Ward councillor id, if known.
            base (float): The unperturbed approval probability.

        Returns:
            list[Lever]: Up to four levers sorted by descending probability gain.
        """
        global_logit = retrieval.global_logit(self.profiles)
        affordable_units = int(application.get("affordable_units", 0) or 0)
        retail_sqft = float(application.get("retail_sqft", 0.0) or 0.0)
        height_m = float(application.get("height_m", 0.0) or 0.0)
        candidates = [
            ("add 12 affordable units", {"affordable_units": affordable_units + 12}),
            ("add ground-floor retail", {"retail_sqft": max(retail_sqft, 3000.0)}),
            ("reduce height by two storeys", {"height_m": height_m - 6.0}),
        ]
        levers: list[Lever] = []
        for change, patch in candidates:
            perturbed = {**application, **patch}
            claims = panel.deterministic_claims(
                perturbed, councillors, self.profiles, staff_signal, ward, global_logit
            )
            scores = [claim["p_yes"] for claim in claims.values()]
            delta = round(poisson_binomial_majority(scores) - base, 4)
            levers.append(Lever(change=change, delta_probability=delta))
        levers.sort(key=lambda lever: lever.delta_probability, reverse=True)
        return levers

    def predict_with_trace(
        self,
        application: dict,
        councillors: list[str],
        staff_recommendation: str = "unknown",
        ward: str | None = None,
        precedent_ids: set[str] | None = None,
    ) -> tuple[VotePrediction, AgentTrace]:
        """Forecast the vote and return both the Contract-1 prediction and the reasoning trace.

        Args:
            application (dict): The Contract 1 ``ApplicationFeatures`` fields.
            councillors (list[str]): Normalized councillor ids on the committee.
            staff_recommendation (str): A key understood by ``config.STAFF_SIGNAL_MAP``.
            ward (str | None): Ward councillor id, if known.
            precedent_ids (set[str] | None): When provided, restrict precedent retrieval to
                these application ids — used by the backtest to keep precedent train-only so
                test-period outcomes cannot leak into the Reasoner's context.

        Returns:
            tuple[VotePrediction, AgentTrace]: The frozen-shape prediction and the additive
            per-councillor reasoning/Skeptic trace.
        """
        staff_signal = config.STAFF_SIGNAL_MAP.get(staff_recommendation, 0.0)
        similar = (
            retrieval.find_similar_applications(application, allowed_ids=precedent_ids)
            if self.use_llm
            else []
        )

        result = panel.run_panel(
            application=application,
            councillors=councillors,
            profiles=self.profiles,
            staff_rec=staff_recommendation,
            staff_signal=staff_signal,
            similar=similar,
            ward=ward,
            use_llm=self.use_llm,
        )
        per = result.per_councillor
        approval = poisson_binomial_majority(list(per.values()))
        levers = self._levers(application, councillors, staff_signal, ward, approval)

        prediction = VotePrediction(
            approval_probability=round(approval, 4),
            per_councillor={cid: round(p, 4) for cid, p in per.items()},
            swing_councillors=swing_councillors(per),
            levers=levers,
        )
        trace = AgentTrace(
            mode=result.mode,
            model=config.LLM_MODEL if result.mode == "panel" else "deterministic-fallback",
            staff_recommendation=staff_recommendation,
            councillors=result.traces,
            precedent_ids=result.precedent_ids,
            n_grounded=sum(1 for t in result.traces if t.grounded),
            n_abstained=sum(1 for t in result.traces if not t.grounded),
        )
        return prediction, trace

    def predict(
        self,
        application: dict,
        councillors: list[str],
        staff_recommendation: str = "unknown",
        ward: str | None = None,
        precedent_ids: set[str] | None = None,
    ) -> VotePrediction:
        """Forecast the council vote for an application (Contract-1 shape).

        Args:
            application (dict): The Contract 1 ``ApplicationFeatures`` fields.
            councillors (list[str]): Normalized councillor ids on the committee.
            staff_recommendation (str): A key understood by ``config.STAFF_SIGNAL_MAP``.
            ward (str | None): Ward councillor id, if known.
            precedent_ids (set[str] | None): Optional precedent restriction (backtest only).

        Returns:
            VotePrediction: Approval probability, per-councillor probabilities, swing
            councillors, and counterfactual levers.
        """
        prediction, _ = self.predict_with_trace(
            application, councillors, staff_recommendation, ward, precedent_ids
        )
        return prediction

"""Token usage tracking for the PM News Agent pipeline.

Accumulates per-step token usage, calculates costs using a
model pricing lookup, and writes a JSON summary to the logs directory.
"""

from datetime import datetime
from pathlib import Path

from models import RunLog, StepUsage

# Pricing per million tokens, keyed by model identifier.
# Update this dict when Anthropic changes pricing or when
# switching to a different model.
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {
        "input_per_million": 3.00,
        "output_per_million": 15.00,
    },
    # Add other models as needed:
    # "claude-haiku-4-5": {"input_per_million": 1.00, "output_per_million": 5.00},
    # "claude-opus-4-6":  {"input_per_million": 5.00, "output_per_million": 25.00},
}


class TokenTracker:
    """Tracks token usage across pipeline steps."""

    def __init__(
        self,
        run_id: str,
        domain: str,
        model: str,
        token_budget: int,
        log_dir: str,
    ):
        """Initialize the tracker.

        Args:
            run_id: Unique identifier for this run.
            domain: Domain description for this run.
            model: Model identifier (must exist in MODEL_PRICING).
            token_budget: Maximum input tokens allowed per run.
            log_dir: Directory to write JSON logs to.

        Raises:
            KeyError: If model is not found in MODEL_PRICING.
        """
        if model not in MODEL_PRICING:
            raise KeyError(
                f"Unknown model '{model}' — add its pricing to "
                f"MODEL_PRICING in token_tracker.py. "
                f"Known models: {list(MODEL_PRICING.keys())}"
            )

        self.run_id = run_id
        self.domain = domain
        self.model = model
        self.token_budget = token_budget
        self.log_dir = log_dir
        self._pricing = MODEL_PRICING[model]
        self._steps: list[StepUsage] = []
        self._started_at = datetime.now()

    def _calculate_cost(
        self, input_tokens: int, output_tokens: int
    ) -> tuple[float, float, float]:
        """Calculate costs for a given token count.

        Returns:
            Tuple of (input_cost, output_cost, total_cost) in USD.
        """
        input_cost = (input_tokens / 1_000_000) * self._pricing["input_per_million"]
        output_cost = (output_tokens / 1_000_000) * self._pricing["output_per_million"]
        return input_cost, output_cost, input_cost + output_cost

    def record(
        self, step_name: str, input_tokens: int, output_tokens: int
    ) -> StepUsage:
        """Record usage for a completed step.

        Args:
            step_name: Identifier for this pipeline step.
            input_tokens: Number of input tokens consumed.
            output_tokens: Number of output tokens generated.

        Returns:
            The StepUsage object created.
        """
        input_cost, output_cost, total_cost = self._calculate_cost(
            input_tokens, output_tokens
        )

        step = StepUsage(
            step_name=step_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_cost_usd=input_cost,
            output_cost_usd=output_cost,
            total_cost_usd=total_cost,
            timestamp=datetime.now(),
        )
        self._steps.append(step)
        return step

    @property
    def total_input_tokens(self) -> int:
        """Accumulated input tokens across all recorded steps."""
        return sum(s.input_tokens for s in self._steps)

    @property
    def total_output_tokens(self) -> int:
        """Accumulated output tokens across all recorded steps."""
        return sum(s.output_tokens for s in self._steps)

    @property
    def total_cost_usd(self) -> float:
        """Accumulated cost across all recorded steps."""
        return sum(s.total_cost_usd for s in self._steps)

    @property
    def budget_remaining(self) -> int:
        """Input tokens remaining before hitting the budget."""
        return max(0, self.token_budget - self.total_input_tokens)

    def would_exceed_budget(self, estimated_input_tokens: int) -> bool:
        """Check if the next call would exceed the token budget.

        Args:
            estimated_input_tokens: Estimated input tokens for the next call.

        Returns:
            True if the next call would push total usage over the budget.
        """
        return (self.total_input_tokens + estimated_input_tokens) > self.token_budget

    def save(self) -> str:
        """Write the RunLog as JSON to logs/{run_id}.json.

        Returns:
            The path to the written file.
        """
        log_dir = Path(self.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        run_log = RunLog(
            run_id=self.run_id,
            domain=self.domain,
            model=self.model,
            token_budget=self.token_budget,
            pricing=self._pricing,
            steps=self._steps,
            total_input_tokens=self.total_input_tokens,
            total_output_tokens=self.total_output_tokens,
            total_cost_usd=self.total_cost_usd,
            budget_remaining=self.budget_remaining,
            started_at=self._started_at,
            completed_at=datetime.now(),
        )

        log_path = log_dir / f"{self.run_id}.json"
        log_path.write_text(run_log.model_dump_json(indent=2))
        return str(log_path)

    def print_summary(self) -> None:
        """Print a human-readable summary to stdout."""
        input_rate = self._pricing["input_per_million"]
        output_rate = self._pricing["output_per_million"]

        print()
        print("═══ Run Summary ═══════════════════════════════════════")
        print(f"  Run ID:    {self.run_id}")
        print(f"  Model:     {self.model}")
        print(f"  Pricing:   ${input_rate:.2f}/M input, ${output_rate:.2f}/M output")
        print("───────────────────────────────────────────────────────")
        print(f"  {'Step':<28} {'Input':>8} {'Output':>8} {'Cost':>10}")
        print("───────────────────────────────────────────────────────")

        for step in self._steps:
            print(
                f"  {step.step_name:<28} "
                f"{step.input_tokens:>8,} "
                f"{step.output_tokens:>8,} "
                f"${step.total_cost_usd:>8.4f}"
            )

        print("───────────────────────────────────────────────────────")
        print(
            f"  {'TOTAL':<28} "
            f"{self.total_input_tokens:>8,} "
            f"{self.total_output_tokens:>8,} "
            f"${self.total_cost_usd:>8.4f}"
        )
        print(f"  Budget remaining: {self.budget_remaining:,} input tokens")

        if self._steps:
            log_path = Path(self.log_dir) / f"{self.run_id}.json"
            print(f"  Log saved: {log_path}")

        print("═══════════════════════════════════════════════════════")
        print()

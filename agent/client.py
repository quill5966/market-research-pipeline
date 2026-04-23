"""Anthropic SDK wrapper for the PM News Agent pipeline.

Thin wrapper around the Anthropic Python SDK that initializes from config,
exposes a call method, and automatically records token usage via the
TokenTracker.
"""

import time

import anthropic

from config import Config
from tracking.token_tracker import TokenTracker


class TokenBudgetExceeded(Exception):
    """Raised when the next LLM call would exceed the configured token budget."""

    def __init__(self, budget: int, used: int, estimated_next: int):
        self.budget = budget
        self.used = used
        self.estimated_next = estimated_next
        super().__init__(
            f"Token budget would be exceeded: {used:,} used + "
            f"~{estimated_next:,} estimated = "
            f"~{used + estimated_next:,} > {budget:,} budget"
        )


class AgentClient:
    """Wrapper around Anthropic SDK with automatic token tracking."""

    def __init__(self, config: Config, tracker: TokenTracker):
        """Initialize the client.

        Args:
            config: Pipeline configuration with API key and model.
            tracker: TokenTracker instance for recording usage.
        """
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self.model = config.model
        self.tracker = tracker

    def call(
        self,
        step_name: str,
        messages: list[dict],
        system: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> str:
        """Make an LLM call, record token usage, and return the text response.

        Args:
            step_name: Identifier for this pipeline step (used in token log).
            messages: List of message dicts [{"role": "user", "content": "..."}].
            system: Optional system prompt.
            max_tokens: Max output tokens for this call.
            temperature: Sampling temperature (0.0 for deterministic).

        Returns:
            The text content of the assistant's response.

        Raises:
            TokenBudgetExceeded: If accumulated input tokens + estimated
                                 next call would exceed the budget.
            anthropic.APIError: On API failures (after retry for rate limits).
        """
        # Budget check — estimate tokens from character count (chars ÷ 4)
        estimated_tokens = len(str(messages)) // 4
        if system:
            estimated_tokens += len(system) // 4

        if self.tracker.would_exceed_budget(estimated_tokens):
            raise TokenBudgetExceeded(
                budget=self.tracker.token_budget,
                used=self.tracker.total_input_tokens,
                estimated_next=estimated_tokens,
            )

        # Build API call kwargs
        kwargs: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system

        # Make the API call with rate limit retry
        response = self._call_with_retry(**kwargs)

        # Record actual token usage
        self.tracker.record(
            step_name=step_name,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

        # Log a warning if actual usage pushed us over budget
        if self.tracker.total_input_tokens > self.tracker.token_budget:
            print(
                f"⚠️  Warning: actual token usage ({self.tracker.total_input_tokens:,}) "
                f"exceeded budget ({self.tracker.token_budget:,}) after step '{step_name}'. "
                f"The budget check uses estimation — actual usage was higher than expected."
            )

        return response.content[0].text

    def _call_with_retry(self, **kwargs) -> anthropic.types.Message:
        """Make an API call with a single retry on rate limit errors.

        Args:
            **kwargs: Arguments to pass to messages.create.

        Returns:
            The API response message.

        Raises:
            anthropic.RateLimitError: If rate limited on both attempts.
            anthropic.APIStatusError: On other API errors.
        """
        try:
            return self.client.messages.create(**kwargs)
        except anthropic.RateLimitError:
            print("⏳ Rate limited — waiting 30s before retry...")
            time.sleep(30)
            return self.client.messages.create(**kwargs)

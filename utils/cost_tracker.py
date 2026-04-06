from dataclasses import dataclass, field

# Prices per 1M tokens (input, output)
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o-mini-search-preview": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-sonnet-4-5": (3.00, 15.00),
}


@dataclass
class AgentUsage:
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class CostTracker:
    def __init__(self) -> None:
        self._usage: dict[str, AgentUsage] = {}

    def record(self, agent_name: str, model: str,
               input_tokens: int, output_tokens: int) -> None:
        if model not in MODEL_PRICING:
            raise ValueError(
                f"Unknown model '{model}'. Add it to MODEL_PRICING in cost_tracker.py"
            )
        input_price, output_price = MODEL_PRICING[model]
        cost = (input_tokens / 1_000_000 * input_price +
                output_tokens / 1_000_000 * output_price)
        self._usage[agent_name] = AgentUsage(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost
        )

    def agent_cost(self, agent_name: str) -> float:
        return self._usage[agent_name].cost_usd if agent_name in self._usage else 0.0

    def total_cost(self) -> float:
        return sum(u.cost_usd for u in self._usage.values())

    def agent_costs_dict(self) -> dict[str, float]:
        return {name: u.cost_usd for name, u in self._usage.items()}

    def models_used_dict(self) -> dict[str, str]:
        return {name: u.model for name, u in self._usage.items()}

    @staticmethod
    def format_usd(amount: float) -> str:
        return f"${amount:.2f}"

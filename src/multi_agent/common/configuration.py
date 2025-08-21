"""Define the configurable parameters for the agent."""
import os
from dataclasses import dataclass, field, fields
from typing import Any, Optional

from langchain_core.runnables import RunnableConfig
from typing_extensions import Annotated

@dataclass(kw_only=True)
class Configuration:
    """Main configuration class for the agent."""

    model: Annotated[str, {"__template_metadata__": {"kind": "llm"}}] = field(
        default="openai/gpt-4o",
        metadata={
            "description": "The name of the language model to use for the agent. "
            "Should be in the form: provider/model-name."
        },
    )

    context_window_size: int = field(
        default=int(os.getenv("CONTEXT_WINDOW_SIZE", "128000")),
        metadata={
            "description": "Size of the context window for the language model. "
            "This is the maximum number of input tokens that can be processed in a single request."
        }
    )

    number_of_events: int = field(
        default=int(os.getenv("NUMBER_OF_EVENTS", "20")),
        metadata={
            "description": "Number of events in the benchmark "
            "This is the number of events to be processed by the agent."
        }
    )

    tokens_budget: int = field(
        default=int(os.getenv("TOKENS_BUDGET", "400000")),
        metadata={
            "description": "Total number of tokens available (as input) for the pcap flow analyzer."
        }
    )

    # Derived fields: not initialized directly
    max_fifo_tokens: int = field(init=False)
    max_working_context_tokens: int = field(init=False)

    def __post_init__(self):
        self.max_fifo_tokens = int(0.92 * self.context_window_size)
        self.max_working_context_tokens = int(0.04 * self.context_window_size)

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "Configuration":
        """Create a Configuration instance from a RunnableConfig."""
        configurable = (
            config["configurable"] if config and "configurable" in config else {}
        )
        values: dict[str, Any] = {
            f.name: os.environ.get(f.name.upper(), configurable.get(f.name))
            for f in fields(cls)
            if f.init
        }

        # Cast to int where needed
        if "context_window_size" in values and isinstance(values["context_window_size"], str):
            values["context_window_size"] = int(values["context_window_size"])
        if "tokens_budget" in values and isinstance(values["tokens_budget"], str):
            values["tokens_budget"] = int(values["tokens_budget"])
        if "number_of_events" in values and isinstance(values["number_of_events"],str):
            values["number_of_events"] = int(values["number_of_events"])

        return cls(**{k: v for k, v in values.items() if v is not None})
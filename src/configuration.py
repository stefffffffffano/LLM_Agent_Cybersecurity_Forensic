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

    max_fifo_tokens: int = field(
    default=int(os.getenv("MAX_FIFO_TOKENS", "110000")),
        metadata={
            "description": "Maximum number of tokens allowed in the FIFO message queue before flushing."
        }
    )

    max_working_context_tokens: int = field(
        default=int(os.getenv("MAX_WORKING_CONTEXT_TOKENS", "5000")),
        metadata={
            "description": "Maximum number of tokens allowed in the working context."
        }
    )

    context_window_size: int = field(
        default=int(os.getenv("CONTEXT_WINDOW_SIZE", "8192")),
        metadata={
            "description": "Size of the context window for the language model. "
            "This is the maximum number of input tokens that can be processed in a single request."
        }
    )

    tokens_budget: int = field(
        default=int(os.getenv("TOKENS_BUDGET", "400000")),
        metadata={
            "description": "Total number of tokens available (as input) for the pcap flow analyzer."
        }
    )

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


         # cast to integer 
        if "max_fifo_tokens" in values and isinstance(values["max_fifo_tokens"], str):
            values["max_fifo_tokens"] = int(values["max_fifo_tokens"])
        if "max_working_context_tokens" in values and isinstance(values["max_working_context_tokens"], str):
            values["max_working_context_tokens"] = int(values["max_working_context_tokens"])
        if "context_window_size" in values and isinstance(values["context_window_size"], str):
            values["context_window_size"] = int(values["context_window_size"])
        if "tokens_budget" in values and isinstance(values["tokens_budget"], str):
            values["tokens_budget"] = int(values["tokens_budget"])
        return cls(**{k: v for k, v in values.items() if v is not None})

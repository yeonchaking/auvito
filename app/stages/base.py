"""Base stage abstraction."""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

InputType = TypeVar("InputType")
OutputType = TypeVar("OutputType")


class BaseStage(ABC, Generic[InputType, OutputType]):
    """Base class for all pipeline stages."""

    stage_name: str

    @abstractmethod
    async def execute(self, input_data: InputType) -> OutputType:
        """Execute the stage.

        Args:
            input_data: Input for this stage

        Returns:
            Output from the stage
        """
        raise NotImplementedError

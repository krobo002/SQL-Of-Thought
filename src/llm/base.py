from abc import ABC, abstractmethod
from typing import Any, Dict, List, Union


class BaseLLM(ABC):
    """
    Abstract base class for all LLM interfaces.
    """

    @abstractmethod
    def __init__(self, model_name: str, **kwargs: Any):
        """
        Initialize the LLM interface.

        Args:
            model_name (str): The name of the model to use.
            **kwargs: Additional keyword arguments for the specific LLM provider.
        """
        self.model_name = model_name

    @abstractmethod
    def invoke(
        self, messages: List[Dict[str, str]], config: Dict[str, Any]
    ) -> Union[str, Dict[str, Any]]:
        """
        Invoke the LLM with a list of messages.

        Args:
            messages (List[Dict[str, str]]): A list of messages to send to the LLM.
            config (Dict[str, Any]): A dictionary of configuration options for the LLM.

        Returns:
            Union[str, Dict[str, Any]]: The response from the LLM.
        """
        pass

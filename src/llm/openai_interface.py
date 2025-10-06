from typing import Any, Dict, List, Union

from openai import OpenAI

from .base import BaseLLM


class OpenAIInterface(BaseLLM):
    """
    LLM interface for OpenAI models.
    """

    def __init__(self, model_name: str, **kwargs: Any):
        """
        Initialize the OpenAI LLM interface.

        Args:
            model_name (str): The name of the model to use.
            **kwargs: Additional keyword arguments for the OpenAI client.
        """
        super().__init__(model_name)
        self.client = OpenAI(**kwargs)

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
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            **config,
        )
        return response.choices[0].message.content

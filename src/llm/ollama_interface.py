import sys
import os

import ollama
from typing import Any, Dict, List, Union
from base import BaseLLM


class OllamaLLM(BaseLLM):
    """
    LLM interface for Ollama models.
    """

    def __init__(self, model_name: str, **kwargs: Any):
        """
        Initialize the Ollama LLM interface.

        Args:
            model_name (str): The name of the model to use.
            **kwargs: Additional keyword arguments for the Ollama client.
        """
        super().__init__(model_name)
        self.client = ollama.Client(**kwargs)

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

        print("Invoking LLM")
        response = self.client.chat(
            model=self.model_name,
            messages=messages,
        )
        return response["message"]["content"]
    
def main():
    model_name = "deepseek-r1:8b"
    llm = OllamaLLM(model_name=model_name)
    # Sample input variables for invoke method
    messages = [
        {"role": "user", "content": "Hello, can you summarize SQL joins?"},
    ]
    config = {
        "think": False
    }
    response = llm.invoke(messages, config=config)
    print(response)

if __name__ == "__main__":
    main()
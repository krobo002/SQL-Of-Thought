from abc import ABC, abstractmethod

class BaseAgent(ABC):
    """
    Base class for all agents in the SQL-of-Thought framework.
    """
    def __init__(self, llm):
        """
        Initializes the agent with a language model interface.
        Args:
            llm: An interface to a large language model.
        """
        self.llm = llm

    @abstractmethod
    def execute(self, *args, **kwargs):
        """
        Executes the agent's task.
        This method should be implemented by all subclasses.
        """
        pass

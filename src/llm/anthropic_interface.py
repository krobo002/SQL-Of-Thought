"""
Anthropic Claude Interface for SQL-of-Thought Framework

This module provides the LLM interface for Anthropic's Claude models,
which achieved the best performance in the SQL-of-Thought paper (91.59% on Spider).
"""

import os
from typing import Any, Dict, List, Union, Optional
import logging

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    anthropic = None

from .base import BaseLLM


class AnthropicInterface(BaseLLM):
    """
    LLM interface for Anthropic Claude models.
    
    According to the SQL-of-Thought paper, Claude Opus 3 achieved the best performance:
    - 91.59% execution accuracy on Spider dataset
    - 90.16% execution accuracy on Spider-Realistic dataset  
    - 82.01% execution accuracy on Spider-SYN dataset
    """

    def __init__(self, 
                 model_name: str = "claude-3-opus-20240229",
                 api_key: Optional[str] = None,
                 max_tokens: int = 4000,
                 temperature: float = 0.0,
                 timeout: int = 30,
                 **kwargs: Any):
        """
        Initialize the Anthropic Claude LLM interface.

        Args:
            model_name: The name of the Claude model to use
            api_key: Anthropic API key (if None, will look for ANTHROPIC_API_KEY env var)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 for deterministic)
            timeout: Request timeout in seconds
            **kwargs: Additional keyword arguments for the Anthropic client
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError(
                "anthropic package is not installed. "
                "Install it with: pip install anthropic"
            )
        
        super().__init__(model_name)
        
        # Get API key from parameter or environment
        if api_key is None:
            api_key = os.getenv("ANTHROPIC_API_KEY")
        
        if not api_key:
            raise ValueError(
                "Anthropic API key is required. "
                "Provide it as a parameter or set ANTHROPIC_API_KEY environment variable."
            )
        
        # Initialize the Anthropic client
        try:
            self.client = anthropic.Anthropic(
                api_key=api_key,
                timeout=timeout,
                **kwargs
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Anthropic client: {str(e)}")
        
        # Store configuration
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Validate model name
        self.supported_models = [
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229", 
            "claude-3-haiku-20240307",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022"
        ]
        
        if model_name not in self.supported_models:
            self.logger.warning(
                f"Model {model_name} may not be supported. "
                f"Supported models: {', '.join(self.supported_models)}"
            )

    def invoke(
        self, messages: List[Dict[str, str]], config: Dict[str, Any] = None
    ) -> Union[str, Dict[str, Any]]:
        """
        Invoke the Claude model with a list of messages.

        Args:
            messages: A list of messages to send to Claude
            config: A dictionary of configuration options for the LLM

        Returns:
            The response content from Claude
        """
        if config is None:
            config = {}
        
        # Merge default config with provided config
        final_config = {
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        final_config.update(config)
        
        # Convert messages to Claude format
        claude_messages = self._convert_messages_format(messages)
        
        try:
            self.logger.debug(f"Sending request to {self.model_name}")
            
            response = self.client.messages.create(
                model=self.model_name,
                messages=claude_messages,
                max_tokens=final_config["max_tokens"],
                temperature=final_config["temperature"],
                **{k: v for k, v in final_config.items() 
                   if k not in ["max_tokens", "temperature"]}
            )
            
            # Extract the content from Claude's response
            if hasattr(response, 'content') and response.content:
                # Claude returns a list of content blocks
                if isinstance(response.content, list) and len(response.content) > 0:
                    # Get the text content from the first block
                    content_block = response.content[0]
                    if hasattr(content_block, 'text'):
                        return content_block.text
                    else:
                        return str(content_block)
                else:
                    return str(response.content)
            else:
                self.logger.warning("No content in Claude response")
                return ""
                
        except anthropic.APIError as e:
            error_msg = f"Anthropic API error: {str(e)}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        except anthropic.APITimeoutError as e:
            error_msg = f"Anthropic API timeout: {str(e)}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        except anthropic.RateLimitError as e:
            error_msg = f"Anthropic rate limit exceeded: {str(e)}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        except Exception as e:
            error_msg = f"Unexpected error calling Anthropic API: {str(e)}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)

    def _convert_messages_format(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Convert messages to Claude's expected format.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            
        Returns:
            List of messages in Claude format
        """
        claude_messages = []
        
        for message in messages:
            if not isinstance(message, dict) or 'role' not in message or 'content' not in message:
                self.logger.warning(f"Invalid message format: {message}")
                continue
            
            role = message['role'].lower()
            content = message['content']
            
            # Claude uses 'user' and 'assistant' roles
            if role in ['user', 'human']:
                claude_role = 'user'
            elif role in ['assistant', 'ai']:
                claude_role = 'assistant'
            elif role == 'system':
                # Claude doesn't have a system role, prepend to first user message
                if claude_messages and claude_messages[-1]['role'] == 'user':
                    claude_messages[-1]['content'] = f"{content}\n\n{claude_messages[-1]['content']}"
                else:
                    claude_messages.append({
                        'role': 'user',
                        'content': content
                    })
                continue
            else:
                self.logger.warning(f"Unknown role '{role}', treating as user")
                claude_role = 'user'
            
            claude_messages.append({
                'role': claude_role,
                'content': content
            })
        
        # Ensure we have at least one message and it starts with user
        if not claude_messages:
            raise ValueError("No valid messages provided")
        
        if claude_messages[0]['role'] != 'user':
            # If first message is not user, add a placeholder user message
            claude_messages.insert(0, {
                'role': 'user',
                'content': "Please proceed with the following:"
            })
        
        return claude_messages

    def predict(self, prompt: str, **kwargs) -> str:
        """
        Simple prediction method for backward compatibility.
        
        Args:
            prompt: The prompt to send to Claude
            **kwargs: Additional configuration options
            
        Returns:
            The response from Claude
        """
        messages = [{"role": "user", "content": prompt}]
        config = kwargs
        
        return self.invoke(messages, config)

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current model.
        
        Returns:
            Dictionary containing model information
        """
        return {
            "provider": "anthropic",
            "model_name": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "timeout": self.timeout,
            "supported_models": self.supported_models,
            "paper_performance": self._get_paper_performance()
        }

    def _get_paper_performance(self) -> Dict[str, Any]:
        """Get performance metrics from the SQL-of-Thought paper"""
        if self.model_name == "claude-3-opus-20240229":
            return {
                "spider_execution_accuracy": 91.59,
                "spider_realistic_execution_accuracy": 90.16,
                "spider_syn_execution_accuracy": 82.01,
                "valid_sql_generation_rate": "94-99%",
                "cost_per_spider_run": 42.58,  # USD
                "total_runtime_hours": 5.0,
                "best_performing_model": True
            }
        else:
            return {
                "best_performing_model": False,
                "note": "Performance metrics available only for claude-3-opus-20240229"
            }

    def estimate_cost(self, 
                     input_tokens: int, 
                     output_tokens: int, 
                     model_name: Optional[str] = None) -> float:
        """
        Estimate the cost of API calls based on token usage.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model_name: Model name (uses instance model if not provided)
            
        Returns:
            Estimated cost in USD
        """
        if model_name is None:
            model_name = self.model_name
        
        # Anthropic pricing as of 2024 (approximate)
        pricing = {
            "claude-3-opus-20240229": {
                "input": 15.00 / 1_000_000,   # $15 per million input tokens
                "output": 75.00 / 1_000_000   # $75 per million output tokens
            },
            "claude-3-sonnet-20240229": {
                "input": 3.00 / 1_000_000,    # $3 per million input tokens
                "output": 15.00 / 1_000_000   # $15 per million output tokens
            },
            "claude-3-haiku-20240307": {
                "input": 0.25 / 1_000_000,    # $0.25 per million input tokens
                "output": 1.25 / 1_000_000    # $1.25 per million output tokens
            },
            "claude-3-5-sonnet-20241022": {
                "input": 3.00 / 1_000_000,    # $3 per million input tokens
                "output": 15.00 / 1_000_000   # $15 per million output tokens
            },
            "claude-3-5-haiku-20241022": {
                "input": 1.00 / 1_000_000,    # $1 per million input tokens
                "output": 5.00 / 1_000_000    # $5 per million output tokens
            }
        }
        
        if model_name not in pricing:
            self.logger.warning(f"Pricing not available for {model_name}, using Opus pricing")
            model_pricing = pricing["claude-3-opus-20240229"]
        else:
            model_pricing = pricing[model_name]
        
        input_cost = input_tokens * model_pricing["input"]
        output_cost = output_tokens * model_pricing["output"]
        
        return input_cost + output_cost


# Convenience function for creating Claude Opus (best performing model)
def create_claude_opus(api_key: Optional[str] = None, **kwargs) -> AnthropicInterface:
    """
    Create an AnthropicInterface configured with Claude-3 Opus (best performing model).
    
    Args:
        api_key: Anthropic API key
        **kwargs: Additional configuration options
        
    Returns:
        AnthropicInterface configured for Claude-3 Opus
    """
    return AnthropicInterface(
        model_name="claude-3-opus-20240229",
        api_key=api_key,
        **kwargs
    )


# Convenience function for creating Claude Sonnet (cost-effective alternative)
def create_claude_sonnet(api_key: Optional[str] = None, **kwargs) -> AnthropicInterface:
    """
    Create an AnthropicInterface configured with Claude-3.5 Sonnet (cost-effective).
    
    Args:
        api_key: Anthropic API key
        **kwargs: Additional configuration options
        
    Returns:
        AnthropicInterface configured for Claude-3.5 Sonnet
    """
    return AnthropicInterface(
        model_name="claude-3-5-sonnet-20241022",
        api_key=api_key,
        **kwargs
    )

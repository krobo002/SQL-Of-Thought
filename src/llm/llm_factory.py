"""
LLM Factory for SQL-of-Thought Framework

Factory pattern implementation for creating LLM instances based on provider configuration.
"""

import yaml
import os
from pathlib import Path
from typing import Dict, Any, Optional

from .base import BaseLLM


class LLMFactory:
    """Factory class for creating LLM instances based on configuration."""
    
    @staticmethod
    def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if config_path is None:
            # Default to config.yaml in the project root
            config_path = Path(__file__).parent.parent.parent / "config.yaml"
        
        with open(config_path, 'r') as file:
            return yaml.safe_load(file)
    
    @staticmethod
    def create_llm(provider: Optional[str] = None, config_path: Optional[str] = None, **kwargs) -> BaseLLM:
        """
        Create an LLM instance based on the provider.
        
        Args:
            provider: LLM provider name ('anthropic', 'openai', 'ollama')
            config_path: Path to configuration file
            **kwargs: Additional arguments to pass to the LLM constructor
            
        Returns:
            BaseLLM instance
            
        Raises:
            ValueError: If provider is not supported
            KeyError: If configuration is missing
        """
        config = LLMFactory.load_config(config_path)
        llm_config = config.get('llm', {})
        
        if provider is None:
            provider = llm_config.get('default_provider', 'anthropic')
        
        # Get provider-specific config
        provider_config = llm_config.get(provider, {})
        
        # Merge global LLM config with provider-specific config
        merged_config = {
            'temperature': llm_config.get('temperature', 0.0),
            'max_tokens': llm_config.get('max_tokens', 4000),
            'timeout': llm_config.get('timeout', 30),
            **provider_config,
            **kwargs  # Allow override of any config
        }
        
        if provider == 'anthropic':
            from .anthropic_interface import AnthropicInterface
            api_key = os.getenv(merged_config.get('api_key_env', 'ANTHROPIC_API_KEY'))
            if not api_key:
                raise ValueError(f"API key not found in environment variable: {merged_config.get('api_key_env', 'ANTHROPIC_API_KEY')}")
            
            return AnthropicInterface(
                api_key=api_key,
                model=merged_config.get('model', 'claude-3-opus-20240229'),
                temperature=merged_config.get('temperature', 0.0),
                max_tokens=merged_config.get('max_tokens', 4000),
                timeout=merged_config.get('timeout', 30)
            )
        
        elif provider == 'openai':
            from .openai_interface import OpenAIInterface
            api_key = os.getenv(merged_config.get('api_key_env', 'OPENAI_API_KEY'))
            if not api_key:
                raise ValueError(f"API key not found in environment variable: {merged_config.get('api_key_env', 'OPENAI_API_KEY')}")
            
            return OpenAIInterface(
                api_key=api_key,
                model=merged_config.get('model', 'gpt-4o'),
                temperature=merged_config.get('temperature', 0.0),
                max_tokens=merged_config.get('max_tokens', 4000),
                timeout=merged_config.get('timeout', 30)
            )
        
        elif provider == 'ollama':
            from .ollama_interface import OllamaInterface
            # Only pass kwargs that the OllamaInterface can handle
            ollama_kwargs = {}
            if 'base_url' in merged_config:
                ollama_kwargs['host'] = merged_config['base_url']  # Ollama uses 'host' not 'base_url'
            if 'timeout' in merged_config:
                ollama_kwargs['timeout'] = merged_config['timeout']
                
            return OllamaInterface(
                model_name=merged_config.get('model', 'llama2'),
                **ollama_kwargs
            )
        
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}. Supported providers: anthropic, openai, ollama")
    
    @staticmethod
    def create_anthropic(model: str = "claude-3-opus-20240229", **kwargs) -> BaseLLM:
        """Convenience method to create Anthropic LLM."""
        return LLMFactory.create_llm('anthropic', model=model, **kwargs)
    
    @staticmethod
    def create_openai(model: str = "gpt-4o", **kwargs) -> BaseLLM:
        """Convenience method to create OpenAI LLM."""
        return LLMFactory.create_llm('openai', model=model, **kwargs)
    
    @staticmethod
    def create_ollama(model: str = "llama2", **kwargs) -> BaseLLM:
        """Convenience method to create Ollama LLM."""
        return LLMFactory.create_llm('ollama', model=model, **kwargs)
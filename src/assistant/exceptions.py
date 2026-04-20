"""Custom exceptions for the personal assistant package."""


class AssistantError(Exception):
    """Base exception for all assistant errors."""


class AuthenticationError(AssistantError):
    """OAuth flow failed or credentials.json is missing."""


class IntegrationError(AssistantError):
    """An external API call returned an unexpected error."""


class LLMError(AssistantError):
    """An Anthropic API call failed."""


class EventNotFoundError(AssistantError):
    """The requested calendar event does not exist."""


class ConfigurationError(AssistantError):
    """A required environment variable or config value is missing."""

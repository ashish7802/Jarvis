# Altron AI Intelligence Layer

## Architecture Overview

The AI layer is built around a provider-agnostic service boundary.

- The application communicates with the LLM through the service layer.
- The service delegates to a provider implementation selected by the factory.
- Groq is implemented as the primary provider, but the contract can support future providers.

## Request Flow

1. The API route receives a chat request.
2. Intent detection classifies the user message.
3. The confidence engine evaluates confidence and ambiguity.
4. The conversation manager builds prompt context from conversation history.
5. The prompt manager loads reusable system and developer prompts.
6. The LLM service sends the prompt to the provider.
7. The provider returns either a complete response or streamed chunks.
8. The route returns a structured response to the client.

## Provider Abstraction

The provider contract is defined by the base provider interface.
It exposes methods for completion, structured response generation, and streaming.
Groq implements this contract while keeping the rest of the application provider-agnostic.

## Conversation Lifecycle

- User messages are appended to the conversation manager.
- Assistant replies are stored separately and in the shared history.
- History is trimmed to a configurable size limit.
- System prompts are composed from reusable prompt templates.

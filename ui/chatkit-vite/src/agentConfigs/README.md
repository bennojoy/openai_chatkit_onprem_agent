# Agent Configurations

This folder contains Realtime Agent configurations for voice-based interactions.

## Available Agents

### Pet Food Store Agent (`petFoodStoreAgent.ts`)

A friendly assistant that helps customers choose the right food for their cats and dogs.

**Features:**
- Greets customers warmly
- Asks relevant questions about their pet
- Provides personalized food recommendations
- Handles age-appropriate nutrition advice
- Addresses special dietary needs

**Voice:** Sage (calm, knowledgeable)

**Example Usage:**
```typescript
import { petFoodStoreAgentConfig } from './agentConfigs';

// Use this config when creating a Realtime API session
const agent = petFoodStoreAgentConfig;
```

## Adding New Agents

To add a new agent:

1. Create a new file: `yourAgentName.ts`
2. Define the agent configuration with:
   - `name`: Unique identifier
   - `voice`: AI voice personality
   - `instructions`: Detailed behavior instructions
   - `tools`: Functions the agent can call
   - `handoffs`: Other agents it can transfer to
3. Export it from `index.ts`

## Agent Configuration Structure

```typescript
{
  name: string;
  voice: "alloy" | "echo" | "sage" | "shimmer" | "verse";
  model: string;
  instructions: string; // Detailed prompt
  tools: Array<{
    name: string;
    description: string;
    parameters?: object;
  }>;
  handoffs: Array<AgentConfig>;
  handoffDescription: string;
  temperature?: number; // 0-1
  maxResponseOutputTokens?: number;
}
```

## Next Steps

These configurations will be used when implementing the voice chat feature with the OpenAI Realtime API.


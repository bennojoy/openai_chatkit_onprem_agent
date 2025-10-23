/**
 * Type definitions for Realtime Agent configurations
 */

export interface AgentTool {
  name: string;
  description: string;
  parameters?: Record<string, any>;
}

export interface AgentConfig {
  name: string;
  voice: "alloy" | "echo" | "sage" | "shimmer" | "verse";
  model: string;
  instructions: string;
  tools: AgentTool[];
  handoffs: any[];
  handoffDescription: string;
  temperature?: number;
  maxResponseOutputTokens?: number;
}


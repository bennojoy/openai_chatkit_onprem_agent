import type { StartScreenPrompt } from "@openai/chatkit";

// =============================================================================
// API Configuration
// =============================================================================

export const API_CONFIG = {
  chatkitServerUrl: "http://localhost:9000/chatkit",
} as const;

// =============================================================================
// App UI Configuration
// =============================================================================

export const APP_UI_CONFIG = {
  title: "PETS INC Demo",
  subtitle: "Powered by Custom ChatKit Server",
  footer: "PETS INC",
} as const;

// =============================================================================
// ChatKit UI Configuration
// =============================================================================

export const CHATKIT_UI_CONFIG = {
  greeting: "Hi! How can I help you today?",
  placeholder: "Type your message here...",
  
  starterPrompts: [
    {
      label: "What can you do?",
      prompt: "What can you do?",
      icon: "circle-question",
    },
    {
      label: "Get started",
      prompt: "Help me get started",
      icon: "sparkle",
    },
  ] as StartScreenPrompt[],
} as const;

// =============================================================================
// Theme Configuration
// =============================================================================

export const THEME_CONFIG = {
  storageKey: "chatkit-theme",
  
  // Light theme configuration
  light: {
    colorScheme: "light" as const,
    color: {
      grayscale: {
        hue: 220,
        tint: 6,
        shade: -4,
      },
      accent: {
        primary: "#0f172a",
        level: 1,
      },
    },
    radius: "round" as const,
  },
  
  // Dark theme configuration
  dark: {
    colorScheme: "dark" as const,
    color: {
      grayscale: {
        hue: 220,
        tint: 6,
        shade: -1,
      },
      accent: {
        primary: "#f1f5f9",
        level: 1,
      },
    },
    radius: "round" as const,
  },
} as const;

// =============================================================================
// Feature Flags (optional)
// =============================================================================

export const FEATURES = {
  enableAttachments: false,
  enableFeedback: false,
  showDebugLogs: true,
} as const;

// =============================================================================
// Helper Functions
// =============================================================================

export function getThemeConfig(scheme: "light" | "dark") {
  return scheme === "dark" ? THEME_CONFIG.dark : THEME_CONFIG.light;
}


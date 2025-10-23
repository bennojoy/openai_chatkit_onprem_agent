import { useState } from "react";
import { ChatKit, useChatKit } from "@openai/chatkit-react";
import { API_CONFIG, CHATKIT_UI_CONFIG, FEATURES, getThemeConfig } from "../lib/config";
import type { ColorScheme } from "../hooks/useColorScheme";

type ChatKitPanelProps = {
  theme: ColorScheme;
  onStartCall?: () => void;
};

function getOrCreateDeviceId(): string {
  let id = localStorage.getItem("deviceId");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("deviceId", id);
  }
  return id;
}

export function ChatKitPanel({ theme, onStartCall }: ChatKitPanelProps) {
  const [error, setError] = useState<string | null>(null);

  const { control } = useChatKit({
    api: {
      url: API_CONFIG.chatkitServerUrl,
      domainKey: "pet-food-assistant", // Required for CustomApiConfig
      uploadStrategy: {
        type: "direct",
        uploadUrl: `${API_CONFIG.chatkitServerUrl}/attachments`,
      },
      fetch: (url, options) => {
        if (FEATURES.showDebugLogs) {
          console.log("[ChatKit] Custom fetch called:", url, options?.method);
        }
        
        return fetch(url, {
          ...options,
          headers: {
            ...options?.headers,
            "user-id": getOrCreateDeviceId(),
            "session-id": "session_123",
            "username": "benno",
          },
        });
      },
    },
    theme: getThemeConfig(theme),
    startScreen: {
      greeting: CHATKIT_UI_CONFIG.greeting,
      prompts: CHATKIT_UI_CONFIG.starterPrompts,
    },
    composer: {
      placeholder: CHATKIT_UI_CONFIG.placeholder,
      attachments: {
        enabled: FEATURES.enableAttachments,
      },
    },
    threadItemActions: {
      feedback: FEATURES.enableFeedback,
    },
    // Temporarily removed onClientTool to test
    // onClientTool: async (toolCall) => {
    //   console.log('Client tool called:', toolCall);
    //   if (toolCall.name === 'voice-call') {
    //     console.log('Voice call tool triggered, calling onStartCall');
    //     // Trigger voice mode
    //     if (onStartCall) {
    //       onStartCall();
    //     } else {
    //       console.error('onStartCall is not defined');
    //     }
    //     return { success: true };
    //   }
    //   return {};
    // },
    header: {
      enabled: true,
      title: {
        text: "Pets Inc Demo",
      },
      rightAction: {
        icon: "dots-vertical",
        onClick: () => {
          if (onStartCall) {
            onStartCall();
          }
        },
      },
    },
    onError: ({ error }: { error: unknown }) => {
      console.error("[ChatKit] error:", error);
    },
  });

  return (
    <div className="relative h-full w-full">
      {error && (
        <div className="absolute top-3 left-3 right-3 p-3 bg-red-50 border border-red-300 rounded-lg z-10">
          <strong>Error:</strong> {error}
        </div>
      )}
      <div style={{ height: '100vh', width: '100%' }}>
        <ChatKit control={control} style={{ height: '100%', width: '100%' }} />
      </div>
    </div>
  );
}


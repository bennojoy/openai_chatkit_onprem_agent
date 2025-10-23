import { useState } from "react";
import { useColorScheme } from "./hooks/useColorScheme";
import { Layout } from "./components/Layout";
import { ChatKitPanel } from "./components/ChatKitPanel";
import { VoicePanel } from "./components/VoicePanel";

type AppMode = "text" | "voice";

export default function App() {
  const { scheme } = useColorScheme();
  const [mode, setMode] = useState<AppMode>("text");

  const handleStartCall = () => {
    setMode("voice");
  };

  const handleEndCall = () => {
    setMode("text");
  };

  return (
    <Layout theme={scheme} mode={mode} onStartCall={handleStartCall}>
      {mode === "text" ? (
        <ChatKitPanel theme={scheme} onStartCall={handleStartCall} />
      ) : (
        <VoicePanel theme={scheme} onEndCall={handleEndCall} />
      )}
    </Layout>
  );
}


import { useState, useEffect, useRef } from "react";
import { RealtimeSession, RealtimeAgent, OpenAIRealtimeWebRTC } from "@openai/agents/realtime";
import { createPetFoodStoreAgent } from "../agentConfigs";
import type { ColorScheme } from "../hooks/useColorScheme";

type VoicePanelProps = {
  theme: ColorScheme;
  onEndCall: () => void;
};

type ConnectionStatus = "connecting" | "connected" | "disconnected" | "error";

type AudioDevice = {
  deviceId: string;
  label: string;
};

type TranscriptItem = {
  id: string;
  role: "user" | "assistant";
  text: string;
  timestamp: Date;
};

export function VoicePanel({ theme, onEndCall }: VoicePanelProps) {
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const [error, setError] = useState<string | null>(null);
  const [devices, setDevices] = useState<AudioDevice[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>("");
  const [showDeviceSelector, setShowDeviceSelector] = useState(true);
  const [transcript, setTranscript] = useState<TranscriptItem[]>([]);
  const [isListening, setIsListening] = useState(false);
  const [username, setUsername] = useState<string>("benno"); // Default username
  
  const sessionRef = useRef<RealtimeSession | null>(null);
  const currentTranscriptRef = useRef<{ [key: string]: string }>({});
  const isDark = theme === "dark";

  useEffect(() => {
    // Load available microphones on mount
    loadAudioDevices();
    return () => {
      disconnect();
    };
  }, []);

  async function loadAudioDevices() {
    try {
      // Request permission first to get device labels
      await navigator.mediaDevices.getUserMedia({ audio: true });
      
      const deviceList = await navigator.mediaDevices.enumerateDevices();
      const audioInputs = deviceList
        .filter(device => device.kind === 'audioinput')
        .map(device => ({
          deviceId: device.deviceId,
          label: device.label || `Microphone ${device.deviceId.slice(0, 5)}`,
        }));
      
      console.log("Available microphones:", audioInputs);
      setDevices(audioInputs);
      
      // Auto-select first device
      if (audioInputs.length > 0) {
        setSelectedDeviceId(audioInputs[0].deviceId);
      }
    } catch (err) {
      console.error("Failed to enumerate devices:", err);
      setError("Microphone access denied");
    }
  }

  function handleStartCall() {
    if (!selectedDeviceId) {
      setError("Please select a microphone");
      return;
    }
    setShowDeviceSelector(false);
    initializeVoiceSession();
  }

  async function initializeVoiceSession() {
    try {
      setStatus("connecting");
      console.log("=== Starting with selected mic:", selectedDeviceId);
      
      // Get ephemeral key from backend
      const sessionConfig = createPetFoodStoreAgent(username);
      const response = await fetch("/api/realtime/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: sessionConfig.model,
          voice: sessionConfig.voice,
          username: username,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to get ephemeral key");
      }

      const data = await response.json();
      const ephemeralKey = data.client_secret?.value || data.value;
      
      if (!ephemeralKey) {
        throw new Error("No ephemeral key in response");
      }
      
      console.log("✓ Ephemeral key received");

      // Get the selected microphone stream
      console.log("Getting microphone stream for device:", selectedDeviceId);
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          deviceId: selectedDeviceId ? { exact: selectedDeviceId } : undefined,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        }
      });
      console.log("✓ Microphone stream obtained");

      // Create agent WITH TOOLS using dynamic configuration
      const agentConfig = createPetFoodStoreAgent(username);
      console.log("Creating agent with config:", {
        name: agentConfig.name,
        username: username,
        toolsCount: agentConfig.tools.length,
        tools: agentConfig.tools.map((t: any) => t.name),
      });
      
      const agent = new RealtimeAgent({
        name: agentConfig.name,
        instructions: agentConfig.instructions,
        tools: agentConfig.tools,  // ← ADD TOOLS!
      });
      console.log("✓ Agent created with", agentConfig.tools.length, "tools and username:", username);
      
      // Create transport with specific media stream
      const transport = new OpenAIRealtimeWebRTC({
        mediaStream: stream,  // ← Use selected microphone!
      });
      console.log("✓ Transport created with selected mic");

      // Create session with transport and agent config
      const session = new RealtimeSession(agent, {
        transport: transport,
        config: {
          inputAudioTranscription: {
            model: "whisper-1",
          },
          turnDetection: {
            type: "server_vad",
            threshold: 0.5,
            prefixPaddingMs: 300,
            silenceDurationMs: 700,
            createResponse: true,
          },
        },
      });
      sessionRef.current = session;
      console.log("✓ Session configured with agent, tools, and auto-response on VAD");

      // Set up event listeners to capture transcripts
      setupEventListeners(session);

      // Connect
      console.log("Connecting...");
      await session.connect({
        apiKey: ephemeralKey,
      });
      
      console.log('You are connected!');
      setStatus("connected");
      
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : "Connection failed");
      setStatus("error");
      setShowDeviceSelector(true); // Show selector again on error
    }
  }

  function setupEventListeners(session: RealtimeSession) {
    console.log("Setting up event listeners for transcripts...");

    session.on("transport_event", (event: any) => {
      const type = event.type;
      
      // Log ALL events to see what we're getting
      console.log("EVENT:", type, event);

      switch (type) {
        case "input_audio_buffer.speech_started":
          console.log("🎙️ You started speaking");
          setIsListening(true);
          break;

        case "input_audio_buffer.speech_stopped":
          console.log("🎙️ You stopped speaking");
          setIsListening(false);
          break;

        case "conversation.item.input_audio_transcription.completed":
          console.log("You said:", event.transcript);
          if (event.transcript) {
            addToTranscript("user", event.transcript);
          }
          break;

        case "response.function_call_arguments.delta":
          console.log("🔧 FUNCTION CALL DELTA:", event);
          break;

        case "response.function_call_arguments.done":
          console.log("🔧 FUNCTION CALL DONE:", event);
          break;

        case "conversation.item.created":
          if (event.item?.type === "function_call") {
            console.log("🔧 FUNCTION CALL ITEM CREATED:", event.item);
          }
          break;

        case "response.output_text.delta":
          console.log("📝 Agent outputting TEXT (NOT calling tool):", event.delta);
          break;

        case "response.output_text.done":
          console.log("📝 Agent finished TEXT output:", event.text);
          break;

        case "response.output_audio_transcript.delta":
          // Accumulate AI response deltas
          if (event.delta && event.item_id) {
            if (!currentTranscriptRef.current[event.item_id]) {
              currentTranscriptRef.current[event.item_id] = "";
            }
            currentTranscriptRef.current[event.item_id] += event.delta;
          }
          break;

        case "response.output_audio_transcript.done":
          // AI finished speaking - show full transcript
          if (event.item_id) {
            const fullText = currentTranscriptRef.current[event.item_id] || event.transcript;
            console.log("AI said:", fullText);
            if (fullText) {
              addToTranscript("assistant", fullText);
            }
            delete currentTranscriptRef.current[event.item_id];
          }
          break;

        case "error":
          console.error("Error:", event.error);
          break;
      }
    });

    console.log("✓ Event listeners ready");
  }

  function addToTranscript(role: "user" | "assistant", text: string) {
    const item: TranscriptItem = {
      id: `${Date.now()}-${Math.random()}`,
      role,
      text,
      timestamp: new Date(),
    };
    setTranscript((prev) => [...prev, item]);
  }

  function disconnect() {
    if (sessionRef.current) {
      sessionRef.current.close();
      sessionRef.current = null;
    }
    setStatus("disconnected");
  }

  // Show device selector before connecting
  if (showDeviceSelector) {
    return (
      <div className="relative h-full w-full flex flex-col items-center justify-center p-6">
        <div className={`w-full max-w-md space-y-6 p-8 rounded-3xl shadow-xl ${
          isDark ? "bg-slate-800/90 ring-1 ring-slate-700/60" : "bg-white/90 ring-1 ring-slate-200/60"
        }`}>
          <div className="text-center">
            <p className="text-2xl mb-2">🎙️</p>
            <h3 className={`text-lg font-semibold mb-2 ${isDark ? "text-slate-100" : "text-slate-900"}`}>
              Select Microphone
            </h3>
            <p className={`text-sm ${isDark ? "text-slate-400" : "text-slate-600"}`}>
              Choose which microphone to use for the call
            </p>
          </div>

          {error && (
            <div className="p-3 bg-red-50 border border-red-300 rounded-lg text-red-800 text-sm">
              <strong>Error:</strong> {error}
            </div>
          )}

          <div className="space-y-3">
            <div>
              <label className={`block text-sm font-medium mb-2 ${isDark ? "text-slate-300" : "text-slate-700"}`}>
                Your Name
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter your name"
                className={`w-full p-3 rounded-xl border transition-colors ${
                  isDark
                    ? "bg-slate-700/50 border-slate-600 text-slate-100 focus:border-slate-500"
                    : "bg-white border-slate-300 text-slate-900 focus:border-slate-400"
                }`}
              />
            </div>
            
            <div>
              <label className={`block text-sm font-medium ${isDark ? "text-slate-300" : "text-slate-700"}`}>
                Available Microphones
              </label>
            {devices.length === 0 ? (
              <p className={`text-sm ${isDark ? "text-slate-400" : "text-slate-600"}`}>
                Loading microphones...
              </p>
            ) : (
              <select
                value={selectedDeviceId}
                onChange={(e) => setSelectedDeviceId(e.target.value)}
                className={`w-full p-3 rounded-xl border transition-colors ${
                  isDark
                    ? "bg-slate-700/50 border-slate-600 text-slate-100 focus:border-slate-500"
                    : "bg-white border-slate-300 text-slate-900 focus:border-slate-400"
                }`}
              >
                {devices.map((device) => (
                  <option key={device.deviceId} value={device.deviceId}>
                    {device.label}
                  </option>
                ))}
              </select>
            )}
            </div>
          </div>

          <button
            onClick={handleStartCall}
            disabled={!selectedDeviceId}
            className={`w-full py-3 px-4 rounded-xl font-medium transition-all shadow-sm ${
              selectedDeviceId
                ? "bg-green-500 hover:bg-green-600 text-white hover:shadow-md"
                : "bg-slate-300 text-slate-500 cursor-not-allowed"
            }`}
          >
            Start Call as {username || "Guest"}
          </button>

          <button
            onClick={() => { disconnect(); onEndCall(); }}
            className={`w-full py-2 px-4 rounded-xl text-sm transition-colors ${
              isDark
                ? "text-slate-400 hover:text-slate-200 hover:bg-slate-700/50"
                : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
            }`}
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  // Call is active - show call interface
  return (
    <div className="relative h-full w-full flex flex-col">
      {/* Header */}
      <div
        className={`flex items-center justify-between p-4 border-b backdrop-blur-sm ${
          isDark ? "border-slate-700/50 bg-slate-800/30" : "border-slate-200/50 bg-slate-50/30"
        }`}
      >
        <div className="flex items-center gap-3">
          {/* Status */}
          <div className="flex items-center gap-2">
            <div
              className={`w-3 h-3 rounded-full ${
                status === "connected"
                  ? "bg-green-500 animate-pulse"
                  : status === "connecting"
                  ? "bg-yellow-500 animate-pulse"
                  : status === "error"
                  ? "bg-red-500"
                  : "bg-gray-500"
              }`}
            />
            <span className={`text-sm font-medium ${isDark ? "text-slate-200" : "text-slate-700"}`}>
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </span>
          </div>

          {/* Microphone indicator */}
          <div className="flex items-center gap-2">
            <span className="text-lg">🎙️</span>
            <span className={`text-sm ${isDark ? "text-slate-400" : "text-slate-600"}`}>
              {isListening ? (
                <span className="font-semibold text-red-500 animate-pulse">Speaking...</span>
              ) : (
                <span>Ready</span>
              )}
            </span>
          </div>
        </div>

        {/* End Call */}
        <button
          onClick={() => { disconnect(); onEndCall(); }}
          className="flex items-center gap-2 px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded-full transition-all shadow-sm hover:shadow-md"
        >
          <span className="text-lg">📞</span>
          <span className="text-sm font-medium">End Call</span>
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className={`mx-4 mt-4 p-3 rounded-xl text-sm ${
          isDark 
            ? "bg-red-900/20 border border-red-800/50 text-red-300"
            : "bg-red-50 border border-red-300 text-red-800"
        }`}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Transcript */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {transcript.length === 0 ? (
          <div className={`text-center py-8 ${isDark ? "text-slate-400" : "text-slate-600"}`}>
            <p className="text-2xl mb-3">🎙️</p>
            <p className="text-lg font-medium mb-2">Voice Call Active</p>
            <p className="text-sm mb-4">Start speaking to talk with our pet food assistant</p>
            <p className={`text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>
              Using: {devices.find(d => d.deviceId === selectedDeviceId)?.label || "Default"}
            </p>
          </div>
        ) : (
          transcript.map((item) => (
            <div
              key={item.id}
              className={`flex ${item.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-3 shadow-sm ${
                  isDark
                    ? "bg-slate-700/80 text-slate-100 ring-1 ring-slate-600/50"
                    : "bg-slate-100 text-slate-900 ring-1 ring-slate-200"
                }`}
              >
                <p className="text-sm leading-relaxed">{item.text}</p>
                <span
                  className={`text-xs mt-1.5 block ${
                    item.role === "user"
                      ? "opacity-70"
                      : isDark
                      ? "text-slate-400"
                      : "text-slate-600"
                  }`}
                >
                  {item.timestamp.toLocaleTimeString()}
                </span>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Footer */}
      <div
        className={`p-4 border-t backdrop-blur-sm ${
          isDark ? "border-slate-700/50 bg-slate-800/30" : "border-slate-200/50 bg-slate-50/30"
        }`}
      >
        <p className={`text-xs text-center ${isDark ? "text-slate-400" : "text-slate-500"}`}>
          🎙️ Voice powered by OpenAI Realtime API • Connected as {username}
        </p>
      </div>
    </div>
  );
}

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
      <div style={{
        position: 'relative',
        width: '100%',
        height: '600px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px',
        background: isDark 
          ? 'linear-gradient(135deg, #1e293b 0%, #0f172a 50%, #1e293b 100%)'
          : 'linear-gradient(135deg, #f8fafc 0%, #ffffff 50%, #f1f5f9 100%)'
      }}>
        <div style={{
          width: '100%',
          maxWidth: '480px',
          padding: '32px',
          borderRadius: '24px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
          background: isDark ? 'rgba(30, 41, 59, 0.95)' : 'rgba(255, 255, 255, 0.95)',
          border: isDark ? '1px solid rgba(71, 85, 105, 0.3)' : '1px solid rgba(226, 232, 240, 0.3)',
          backdropFilter: 'blur(10px)'
        }}>
          <div style={{ textAlign: 'center', marginBottom: '32px' }}>
            <div style={{ fontSize: '48px', marginBottom: '16px' }}>🎙️</div>
            <h3 style={{
              fontSize: '24px',
              fontWeight: '600',
              marginBottom: '8px',
              color: isDark ? '#f1f5f9' : '#0f172a'
            }}>
              Select Microphone
            </h3>
            <p style={{
              fontSize: '16px',
              color: isDark ? '#94a3b8' : '#64748b',
              margin: 0
            }}>
              Choose which microphone to use for the call
            </p>
          </div>

          {error && (
            <div style={{
              padding: '16px',
              backgroundColor: '#fef2f2',
              border: '1px solid #fecaca',
              borderRadius: '12px',
              color: '#991b1b',
              fontSize: '14px',
              marginBottom: '24px'
            }}>
              <strong>Error:</strong> {error}
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <div>
              <label style={{
                display: 'block',
                fontSize: '16px',
                fontWeight: '500',
                marginBottom: '12px',
                color: isDark ? '#cbd5e1' : '#374151'
              }}>
                Your Name
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter your name"
                style={{
                  width: '100%',
                  padding: '16px',
                  borderRadius: '12px',
                  border: `2px solid ${isDark ? '#475569' : '#d1d5db'}`,
                  backgroundColor: isDark ? '#374151' : '#ffffff',
                  color: isDark ? '#f1f5f9' : '#111827',
                  fontSize: '16px',
                  outline: 'none',
                  transition: 'all 0.2s ease',
                  boxSizing: 'border-box'
                }}
                onFocus={(e) => {
                  const target = e.target as HTMLInputElement;
                  target.style.borderColor = isDark ? '#64748b' : '#94a3b8';
                  target.style.backgroundColor = isDark ? '#4b5563' : '#f9fafb';
                }}
                onBlur={(e) => {
                  const target = e.target as HTMLInputElement;
                  target.style.borderColor = isDark ? '#475569' : '#d1d5db';
                  target.style.backgroundColor = isDark ? '#374151' : '#ffffff';
                }}
              />
            </div>
            
            <div>
              <label style={{
                display: 'block',
                fontSize: '16px',
                fontWeight: '500',
                marginBottom: '12px',
                color: isDark ? '#cbd5e1' : '#374151'
              }}>
                Available Microphones
              </label>
              {devices.length === 0 ? (
                <p style={{
                  fontSize: '16px',
                  color: isDark ? '#94a3b8' : '#64748b',
                  margin: 0,
                  padding: '16px',
                  backgroundColor: isDark ? '#374151' : '#f9fafb',
                  borderRadius: '12px',
                  border: `2px solid ${isDark ? '#475569' : '#d1d5db'}`
                }}>
                  Loading microphones...
                </p>
              ) : (
                <select
                  value={selectedDeviceId}
                  onChange={(e) => setSelectedDeviceId(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '16px',
                    borderRadius: '12px',
                    border: `2px solid ${isDark ? '#475569' : '#d1d5db'}`,
                    backgroundColor: isDark ? '#374151' : '#ffffff',
                    color: isDark ? '#f1f5f9' : '#111827',
                    fontSize: '16px',
                    outline: 'none',
                    transition: 'all 0.2s ease',
                    boxSizing: 'border-box',
                    cursor: 'pointer'
                  }}
                  onFocus={(e) => {
                    const target = e.target as HTMLSelectElement;
                    target.style.borderColor = isDark ? '#64748b' : '#94a3b8';
                    target.style.backgroundColor = isDark ? '#4b5563' : '#f9fafb';
                  }}
                  onBlur={(e) => {
                    const target = e.target as HTMLSelectElement;
                    target.style.borderColor = isDark ? '#475569' : '#d1d5db';
                    target.style.backgroundColor = isDark ? '#374151' : '#ffffff';
                  }}
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

          <div style={{ marginTop: '32px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <button
              onClick={handleStartCall}
              disabled={!selectedDeviceId}
              style={{
                width: '100%',
                padding: '16px 24px',
                borderRadius: '12px',
                border: 'none',
                fontSize: '18px',
                fontWeight: '600',
                cursor: selectedDeviceId ? 'pointer' : 'not-allowed',
                transition: 'all 0.2s ease',
                backgroundColor: selectedDeviceId ? '#10b981' : '#cbd5e1',
                color: selectedDeviceId ? '#ffffff' : '#6b7280',
                boxShadow: selectedDeviceId ? '0 4px 14px 0 rgba(16, 185, 129, 0.3)' : 'none'
              }}
              onMouseEnter={(e) => {
                if (selectedDeviceId) {
                  const target = e.target as HTMLButtonElement;
                  target.style.backgroundColor = '#059669';
                  target.style.transform = 'translateY(-2px)';
                  target.style.boxShadow = '0 8px 25px 0 rgba(16, 185, 129, 0.4)';
                }
              }}
              onMouseLeave={(e) => {
                if (selectedDeviceId) {
                  const target = e.target as HTMLButtonElement;
                  target.style.backgroundColor = '#10b981';
                  target.style.transform = 'translateY(0)';
                  target.style.boxShadow = '0 4px 14px 0 rgba(16, 185, 129, 0.3)';
                }
              }}
            >
              Start Call as {username || "Guest"}
            </button>

            <button
              onClick={() => { disconnect(); onEndCall(); }}
              style={{
                width: '100%',
                padding: '12px 24px',
                borderRadius: '12px',
                border: `2px solid ${isDark ? '#475569' : '#d1d5db'}`,
                backgroundColor: 'transparent',
                color: isDark ? '#94a3b8' : '#6b7280',
                fontSize: '16px',
                fontWeight: '500',
                cursor: 'pointer',
                transition: 'all 0.2s ease'
              }}
              onMouseEnter={(e) => {
                const target = e.target as HTMLButtonElement;
                target.style.backgroundColor = isDark ? '#374151' : '#f9fafb';
                target.style.color = isDark ? '#cbd5e1' : '#374151';
                target.style.borderColor = isDark ? '#64748b' : '#94a3b8';
              }}
              onMouseLeave={(e) => {
                const target = e.target as HTMLButtonElement;
                target.style.backgroundColor = 'transparent';
                target.style.color = isDark ? '#94a3b8' : '#6b7280';
                target.style.borderColor = isDark ? '#475569' : '#d1d5db';
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Call is active - show call interface
  return (
    <div style={{
      position: 'relative',
      width: '100%',
      height: '600px',
      display: 'flex',
      flexDirection: 'column',
      background: isDark 
        ? 'linear-gradient(135deg, #1e293b 0%, #0f172a 50%, #1e293b 100%)'
        : 'linear-gradient(135deg, #f8fafc 0%, #ffffff 50%, #f1f5f9 100%)'
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '16px 24px',
        borderBottom: isDark ? '1px solid rgba(71, 85, 105, 0.3)' : '1px solid rgba(226, 232, 240, 0.3)',
        background: isDark ? 'rgba(30, 41, 59, 0.3)' : 'rgba(248, 250, 252, 0.3)',
        backdropFilter: 'blur(10px)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
          {/* Status */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{
              width: '12px',
              height: '12px',
              borderRadius: '50%',
              backgroundColor: status === "connected" ? '#10b981' : 
                               status === "connecting" ? '#f59e0b' : 
                               status === "error" ? '#ef4444' : '#6b7280',
              animation: (status === "connected" || status === "connecting") ? 'pulse 2s infinite' : 'none'
            }} />
            <span style={{
              fontSize: '14px',
              fontWeight: '500',
              color: isDark ? '#e2e8f0' : '#374151'
            }}>
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </span>
          </div>

          {/* Microphone indicator */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '18px' }}>🎙️</span>
            <span style={{
              fontSize: '14px',
              color: isDark ? '#94a3b8' : '#64748b'
            }}>
              {isListening ? (
                <span style={{
                  fontWeight: '600',
                  color: '#ef4444',
                  animation: 'pulse 1s infinite'
                }}>Speaking...</span>
              ) : (
                <span>Ready</span>
              )}
            </span>
          </div>
        </div>

        {/* End Call */}
        <button
          onClick={() => { disconnect(); onEndCall(); }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 16px',
            backgroundColor: '#ef4444',
            color: '#ffffff',
            border: 'none',
            borderRadius: '24px',
            fontSize: '14px',
            fontWeight: '500',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            boxShadow: '0 2px 8px rgba(239, 68, 68, 0.3)'
          }}
          onMouseEnter={(e) => {
            const target = e.target as HTMLButtonElement;
            target.style.backgroundColor = '#dc2626';
            target.style.transform = 'translateY(-1px)';
            target.style.boxShadow = '0 4px 12px rgba(239, 68, 68, 0.4)';
          }}
          onMouseLeave={(e) => {
            const target = e.target as HTMLButtonElement;
            target.style.backgroundColor = '#ef4444';
            target.style.transform = 'translateY(0)';
            target.style.boxShadow = '0 2px 8px rgba(239, 68, 68, 0.3)';
          }}
        >
          <span style={{ fontSize: '18px' }}>📞</span>
          <span>End Call</span>
        </button>
      </div>

      {/* Error */}
      {error && (
        <div style={{
          margin: '16px 24px',
          padding: '16px',
          borderRadius: '12px',
          backgroundColor: isDark ? 'rgba(127, 29, 29, 0.2)' : '#fef2f2',
          border: isDark ? '1px solid rgba(185, 28, 28, 0.3)' : '1px solid #fecaca',
          color: isDark ? '#fca5a5' : '#991b1b',
          fontSize: '14px'
        }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Transcript */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '24px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px'
      }}>
        {transcript.length === 0 ? (
          <div style={{
            textAlign: 'center',
            padding: '64px 0',
            color: isDark ? '#94a3b8' : '#64748b'
          }}>
            <div style={{ fontSize: '48px', marginBottom: '24px' }}>🎙️</div>
            <div style={{ fontSize: '20px', fontWeight: '500', marginBottom: '8px', color: isDark ? '#e2e8f0' : '#374151' }}>
              Voice Call Active
            </div>
            <div style={{ fontSize: '16px', marginBottom: '16px' }}>
              Start speaking to talk with our pet food assistant
            </div>
            <div style={{ fontSize: '14px', color: isDark ? '#64748b' : '#9ca3af' }}>
              Using: {devices.find(d => d.deviceId === selectedDeviceId)?.label || "Default"}
            </div>
          </div>
        ) : (
          transcript.map((item) => (
            <div
              key={item.id}
              style={{
                display: 'flex',
                justifyContent: item.role === "user" ? "flex-end" : "flex-start"
              }}
            >
              <div style={{
                maxWidth: '80%',
                borderRadius: '16px',
                padding: '16px 20px',
                boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)',
                background: isDark 
                  ? 'rgba(51, 65, 85, 0.8)' 
                  : 'rgba(241, 245, 249, 0.8)',
                color: isDark ? '#f1f5f9' : '#111827',
                border: isDark ? '1px solid rgba(71, 85, 105, 0.3)' : '1px solid rgba(226, 232, 240, 0.3)',
                backdropFilter: 'blur(10px)'
              }}>
                <p style={{
                  fontSize: '16px',
                  lineHeight: '1.5',
                  margin: 0,
                  marginBottom: '8px'
                }}>{item.text}</p>
                <span style={{
                  fontSize: '12px',
                  color: item.role === "user" 
                    ? 'rgba(255, 255, 255, 0.7)' 
                    : isDark ? '#94a3b8' : '#64748b',
                  display: 'block'
                }}>
                  {item.timestamp.toLocaleTimeString()}
                </span>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Footer */}
      <div style={{
        padding: '16px 24px',
        borderTop: isDark ? '1px solid rgba(71, 85, 105, 0.3)' : '1px solid rgba(226, 232, 240, 0.3)',
        background: isDark ? 'rgba(30, 41, 59, 0.3)' : 'rgba(248, 250, 252, 0.3)',
        backdropFilter: 'blur(10px)'
      }}>
        <p style={{
          fontSize: '12px',
          textAlign: 'center',
          margin: 0,
          color: isDark ? '#94a3b8' : '#64748b'
        }}>
          🎙️ Voice powered by OpenAI Realtime API • Connected as {username}
        </p>
      </div>
    </div>
  );
}

# OpenAI ChatKit + Voice Agent Demo

A full-stack application demonstrating **OpenAI ChatKit** (text chat) and **OpenAI Realtime API** (voice chat) with a **multi-agent architecture** for a pet food store. The voice agent acts as a concierge and delegates product searches to specialized agents using OpenAI Prompts and MCP tools.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (Vite + React + TypeScript)                  │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Text Chat: OpenAI ChatKit Web Component         │  │
│  │  Voice Chat: OpenAI Realtime API                 │  │
│  │  ├── Concierge Agent (handles all conversations) │  │
│  │  └── Product Search Tool (calls backend)         │  │
│  └────┼─────────────────────────────────────────────┘  │
└───────┼────────────────────────────────────────────────┘
        │ HTTP API calls
        ↓
┌─────────────────────────────────────────────────────────┐
│  Backend (FastAPI + Python)                            │
│  ┌───────────────────────────────────────────────────┐  │
│  │  ChatKit Sessions (/api/chatkit/session)         │  │
│  │  Realtime Sessions (/api/realtime/session)       │  │
│  │  Product Search (/api/agents/product-search)     │  │
│  │  ├── Uses OpenAI Prompt API                      │  │
│  │  └── Integrates with MCP tools                   │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## 🚀 Features

### Text Chat (ChatKit)
- **OpenAI Workflows integration** with pre-configured workflows
- **Modular UI components** with dark/light theme support
- **Real-time messaging** with OpenAI's ChatKit web component

### Voice Chat (Realtime API)
- **Real-time voice conversations** with OpenAI Realtime API
- **Microphone selection** - choose your audio input device
- **Live transcription** - see conversation history in real-time
- **Multi-agent architecture**:
  - **Concierge Agent**: Handles all customer interactions
  - **Product Search Agent**: Specialized agent using OpenAI Prompts + MCP tools

### Multi-Agent Flow
1. **Customer speaks** to concierge agent
2. **Concierge decides** if product search is needed
3. **Tool delegation** to backend product search agent
4. **OpenAI Prompt** processes query with MCP tools
5. **Results returned** to concierge who speaks to customer

## 📋 Prerequisites

- **Node.js** 18+ and **npm**
- **Python** 3.8+ and **pip**
- **OpenAI API Key** with access to:
  - ChatKit (Workflows)
  - Realtime API
  - Responses API (Prompts)
- **MCP Server** (optional, for product search tools)

## 🛠️ Setup

### 1. Clone and Install Dependencies

```bash
git clone <your-repo>
cd oai_chatkit

# Backend dependencies
pip install fastapi uvicorn requests openai python-multipart

# Frontend dependencies
cd chatkit-vite
npm install
```

### 2. Environment Variables

Create a `.env` file in the root directory:

```bash
# Required
OPENAI_API_KEY=sk-your-openai-api-key
CHATKIT_WORKFLOW_ID=wf_your-workflow-id

# Optional (for product search with MCP tools)
MCP_SERVER_URL=https://your-ngrok-url.ngrok-free.app/your-path
MCP_AUTHORIZATION=your-mcp-auth-token
```

### 3. Start the Backend Server

```bash
cd /path/to/oai_chatkit
python session_server.py
```

The backend will start on `http://localhost:8000`

### 4. Start the Frontend

```bash
cd /path/to/oai_chatkit/chatkit-vite
npm run dev
```

The frontend will start on `http://localhost:5173`

## 🎯 Usage

### Text Chat
1. Open `http://localhost:5173`
2. The ChatKit interface loads automatically
3. Type messages and get responses from your OpenAI Workflow

### Voice Chat
1. Click the **"Call"** button in the top-right
2. **Select your microphone** from the dropdown
3. **Start speaking** - the concierge will greet you
4. **Ask about products** - e.g., "What dog food do you have for sensitive stomachs?"
5. The concierge will call the product search agent and return results

### Example Conversations

**General Chat (No Tool Called):**
```
You: "Hi, I have a dog"
Concierge: "Welcome to PETS INC! I'd love to help you find the perfect food for your furry friend. How old is your dog?"
```

**Product Search (Tool Called):**
```
You: "What dog food do you have for sensitive stomachs?"
Concierge: "Let me search our product database for you..."
[Backend calls OpenAI Prompt with MCP tools]
Concierge: "Great! I found 3 options: Hill's Science Diet Sensitive Stomach ($44.99)..."
```

## 🔧 API Endpoints

### ChatKit Session
```http
POST /api/chatkit/session
Content-Type: application/json

{
  "user": "user-id-or-device-id"
}
```

**Response:**
```json
{
  "client_secret": "ck_..."
}
```

### Realtime Session
```http
POST /api/realtime/session
Content-Type: application/json

{
  "model": "gpt-4o-realtime-preview-2025-06-03",
  "voice": "sage"
}
```

**Response:**
```json
{
  "client_secret": "ek_..."
}
```

### Product Search
```http
POST /api/agents/product-search
Content-Type: application/json

{
  "query": "dog food for sensitive stomachs"
}
```

**Response:**
```json
{
  "status": "success",
  "response": "Based on your dog's sensitive stomach, I recommend...",
  "query": "dog food for sensitive stomachs"
}
```

## 📁 Project Structure

```
oai_chatkit/
├── session_server.py              # FastAPI backend server
├── chatkit-vite/                  # Frontend React app
│   ├── src/
│   │   ├── components/
│   │   │   ├── Layout.tsx         # Main layout with header/footer
│   │   │   ├── ChatKitPanel.tsx   # Text chat interface
│   │   │   └── VoicePanel.tsx     # Voice chat interface
│   │   ├── agentConfigs/
│   │   │   └── petFoodStoreAgent.ts # Concierge agent + tool config
│   │   ├── hooks/
│   │   │   └── useColorScheme.ts  # Theme management
│   │   ├── lib/
│   │   │   └── config.ts          # Centralized configuration
│   │   └── App.tsx                # Main app component
│   ├── index.html                 # HTML with ChatKit script
│   └── package.json
└── README.md
```

## 🎨 Customization

### Agent Configuration

Edit `chatkit-vite/src/agentConfigs/petFoodStoreAgent.ts`:

```typescript
export const petFoodStoreAgentConfig = {
  name: "petFoodConcierge",
  instructions: `You are a friendly concierge at PETS INC...`,
  tools: [productSearchTool],
  // ... other config
};
```

### UI Configuration

Edit `chatkit-vite/src/lib/config.ts`:

```typescript
export const APP_UI_CONFIG = {
  title: "Your App Name",
  subtitle: "Powered by OpenAI",
  footer: "Your Company",
};
```

### Product Search Prompt

Update the prompt ID and version in `session_server.py`:

```python
PRODUCT_SEARCH_PROMPT_ID = "pmpt_your-prompt-id"
PRODUCT_SEARCH_PROMPT_VERSION = "2"
```

## 🐛 Troubleshooting

### Common Issues

**1. Blank Screen in Frontend**
- Check browser console for errors
- Ensure ChatKit script is loaded in `index.html`
- Verify Tailwind CSS is installed

**2. Voice Chat Not Working**
- Check microphone permissions
- Verify backend is running on port 8000
- Check console for WebRTC connection errors

**3. Product Search 500 Error**
- Verify `MCP_SERVER_URL` and `MCP_AUTHORIZATION` are set
- Check if ngrok tunnel is running (if using MCP tools)
- Verify OpenAI Prompt ID and version are correct

**4. Tool Not Being Called**
- Check browser console for "Agent created with X tools"
- Verify tool description matches user queries
- Check if agent instructions mention when to use tools

### Debug Logging

The application includes extensive logging:

**Frontend (Browser Console):**
```
✓ Agent created with 1 tools
🔧 TOOL EXECUTE CALLED: searchProducts
📝 Agent outputting TEXT (NOT calling tool)
```

**Backend (Terminal):**
```
======================================================================
🔧 PRODUCT SEARCH ENDPOINT HIT
======================================================================
📥 Received query: dog food for sensitive stomachs
✅ PRODUCT SEARCH completed successfully
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is for demonstration purposes. Please check OpenAI's terms of service for production use.

## 🙏 Acknowledgments

- **OpenAI** for ChatKit, Realtime API, and Agents SDK
- **FastAPI** for the Python backend
- **Vite + React** for the frontend
- **Tailwind CSS** for styling

---

## 🔗 Related Resources

- [OpenAI ChatKit Documentation](https://platform.openai.com/docs/guides/chatkit)
- [OpenAI Realtime API Documentation](https://platform.openai.com/docs/guides/realtime)
- [OpenAI Agents SDK](https://github.com/openai/openai-agents-js)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Vite Documentation](https://vitejs.dev/)

---

**Happy coding! 🚀**

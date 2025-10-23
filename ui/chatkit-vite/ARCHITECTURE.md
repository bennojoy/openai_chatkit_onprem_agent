# ChatKit Application Architecture

## 📐 Component Hierarchy

```
main.tsx
  └── App.tsx
      └── useColorScheme() hook
      └── Layout
          └── ChatKitPanel
              └── useChatKit() hook
                  └── config.ts
```

## 🔄 Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                         User Browser                         │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  App.tsx                                           │    │
│  │  - Manages theme state                             │    │
│  │  - Orchestrates components                         │    │
│  └───┬──────────────────────────────────────────┬─────┘    │
│      │                                          │           │
│  ┌───▼────────────────┐              ┌─────────▼─────┐    │
│  │  Layout            │              │  useColorScheme│    │
│  │  - Page structure  │◄─────────────┤  - Theme logic │    │
│  │  - Styling wrapper │              │  - localStorage│    │
│  └───┬────────────────┘              └────────────────┘    │
│      │                                                      │
│  ┌───▼──────────────────────────────────────┐             │
│  │  ChatKitPanel                            │             │
│  │  - Session management                    │             │
│  │  - API communication                     │             │
│  │  - Error handling                        │             │
│  └───┬────────────────────┬─────────────────┘             │
│      │                    │                                │
│  ┌───▼────────┐      ┌────▼──────────┐                    │
│  │ config.ts  │      │  ChatKit SDK  │                    │
│  │ - Settings │      │  - UI render  │                    │
│  └────────────┘      └───────┬───────┘                    │
└────────────────────────────┼──┼──────────────────────────┘
                              │  │
                              │  └─────► OpenAI ChatKit API
                              │
                    ┌─────────▼──────────┐
                    │   FastAPI Backend  │
                    │   session_server.py│
                    └─────────┬──────────┘
                              │
                    ┌─────────▼─────────┐
                    │  OpenAI Sessions  │
                    │  API              │
                    └───────────────────┘
```

## 🗂️ File Responsibilities

### **App.tsx** (Entry Point)
```typescript
Responsibilities:
- Initialize theme system
- Render layout and chat
- Top-level state management

Dependencies:
→ hooks/useColorScheme
→ components/Layout
→ components/ChatKitPanel
```

### **lib/config.ts** (Configuration)
```typescript
Exports:
- API_CONFIG (endpoints)
- CHATKIT_UI_CONFIG (text, prompts)
- THEME_CONFIG (colors, styles)
- FEATURES (flags)
- getThemeConfig() helper

Used by:
← components/ChatKitPanel
← hooks/useColorScheme
```

### **hooks/useColorScheme.ts** (State Hook)
```typescript
Responsibilities:
- Detect system theme
- Persist to localStorage
- Apply dark class to DOM

Returns:
{ scheme, toggle, setScheme }

Used by:
← App.tsx
```

### **components/Layout.tsx** (UI Wrapper)
```typescript
Responsibilities:
- Page layout structure
- Theme-aware backgrounds
- Header/Footer rendering

Props:
- theme: ColorScheme
- children: ReactNode
```

### **components/ChatKitPanel.tsx** (Chat Interface)
```typescript
Responsibilities:
- ChatKit integration
- Session API calls
- Error handling
- UI configuration

Props:
- theme: ColorScheme

Uses:
→ lib/config.ts
→ @openai/chatkit-react
```

## 🔌 External Dependencies

### Frontend
- **React** - UI framework
- **@openai/chatkit-react** - ChatKit React integration
- **@openai/chatkit** - Type definitions
- **Vite** - Build tool

### Backend
- **FastAPI** - Python web framework
- **Uvicorn** - ASGI server
- **Requests** - HTTP client
- **OpenAI API** - Session management

## 🌐 API Communication

### Session Creation Flow:
```
1. User opens app
   ↓
2. ChatKitPanel.getClientSecret() called
   ↓
3. POST /api/chatkit/session
   body: { user: "device-id" }
   ↓
4. FastAPI forwards to OpenAI
   POST https://api.openai.com/v1/chatkit/sessions
   ↓
5. OpenAI returns client_secret
   ↓
6. Frontend receives client_secret
   ↓
7. ChatKit initializes with secret
   ↓
8. User can chat!
```

## 🎨 Styling Architecture

### CSS Organization:
```
index.css (Global)
- Base resets
- Dark mode classes
- Scrollbar styles

components/Layout.tsx (Component)
- Inline Tailwind-like classes
- Dynamic theme-based styles

components/ChatKitPanel.tsx (Component)
- Error display styles
- Container sizing
```

### Theme System:
```
System/User Preference
  ↓
useColorScheme hook
  ↓
localStorage persistence
  ↓
<html class="dark">
  ↓
CSS: .dark { ... }
  ↓
Theme-aware components
```

## 🔐 Environment Configuration

### Frontend (Vite):
```bash
# Optional: If you need custom env vars
VITE_API_URL=http://localhost:8000
```

### Backend (FastAPI):
```bash
# Required
OPENAI_API_KEY=sk-...
CHATKIT_WORKFLOW_ID=wf_...
```

## 📦 Build & Deployment

### Development:
```bash
# Terminal 1: Backend
python session_server.py

# Terminal 2: Frontend
npm run dev
```

### Production:
```bash
# Build frontend
npm run build

# Serve with any static host
# Backend needs production ASGI server
```

## 🧩 Extension Points

Want to add features? Here's where to start:

### Add a new widget:
1. Create `components/YourWidget.tsx`
2. Import in `Layout.tsx` or `App.tsx`
3. Pass theme as prop

### Add new API endpoint:
1. Add to `API_CONFIG` in `lib/config.ts`
2. Create fetch function in `lib/api.ts` (if needed)
3. Use in component

### Add custom theme:
1. Add config to `THEME_CONFIG` in `lib/config.ts`
2. Create new color scheme
3. Use in `getThemeConfig()`

### Add custom hook:
1. Create `hooks/useYourHook.ts`
2. Export hook function
3. Use in components

## 🎯 Best Practices

1. **Always use config.ts** for magic strings
2. **Keep components small** (< 150 lines)
3. **Extract hooks** for reusable logic
4. **Type everything** with TypeScript
5. **Document complex logic** with comments
6. **Test in both themes** (light/dark)


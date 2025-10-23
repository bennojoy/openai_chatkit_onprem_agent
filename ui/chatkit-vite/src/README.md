# Source Structure

This directory contains the modularized ChatKit application.

## 📁 Folder Structure

```
src/
├── components/          # React components
│   ├── ChatKitPanel.tsx    # Main chat interface component
│   └── Layout.tsx          # Page layout wrapper
│
├── hooks/               # Custom React hooks
│   └── useColorScheme.ts   # Theme management hook
│
├── lib/                 # Configuration and utilities
│   └── config.ts           # All app configuration (API, UI, themes)
│
├── types/               # TypeScript type definitions
│   └── index.ts            # Shared types
│
├── App.tsx              # Main application component
├── main.tsx             # Application entry point
├── index.css            # Global styles
└── App.css              # Component-specific styles
```

## 🎯 Key Files

### `lib/config.ts`
Central configuration file containing:
- API endpoints
- ChatKit UI settings (greetings, prompts, placeholders)
- Theme configurations (light/dark)
- Feature flags

**To customize the app, start here!**

### `hooks/useColorScheme.ts`
Manages theme state:
- Persists theme to localStorage
- Syncs with system preferences
- Applies dark mode class to HTML

### `components/ChatKitPanel.tsx`
The ChatKit integration component:
- Handles session creation
- Manages ChatKit configuration
- Error handling

### `components/Layout.tsx`
Page layout wrapper:
- Responsive container
- Theme-aware styling
- Header and footer

## 🚀 How to Add Features

### Add a new configuration option:
1. Edit `lib/config.ts`
2. Add your config to the appropriate section
3. Use it in your components

### Add a new component:
1. Create `components/YourComponent.tsx`
2. Import it in `App.tsx` or other components
3. Pass theme via props if needed

### Add a new hook:
1. Create `hooks/useYourHook.ts`
2. Import and use in components

### Customize the theme:
1. Edit `THEME_CONFIG` in `lib/config.ts`
2. Modify colors, radius, etc.
3. Changes apply automatically

## 🎨 Styling

The app uses:
- Inline Tailwind-like classes (className)
- CSS-in-JS for dynamic styles
- Global styles in `index.css`
- Theme-aware color schemes

## 🔧 Environment Variables

Set these in your `.env` file:
- `VITE_API_URL` - Backend API URL (optional)


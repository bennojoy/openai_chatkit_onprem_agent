import type { ReactNode } from "react";
import type { ColorScheme } from "../hooks/useColorScheme";
import { APP_UI_CONFIG } from "../lib/config";

type LayoutProps = {
  theme: ColorScheme;
  mode: "text" | "voice";
  onStartCall: () => void;
  children: ReactNode;
};

export function Layout({ theme, mode, onStartCall, children }: LayoutProps) {
  const isDark = theme === "dark";
  const isInCall = mode === "voice";

  return (
    <div
      className={`min-h-screen bg-gradient-to-br transition-colors duration-300 ${
        isDark
          ? "from-slate-900 via-slate-950 to-slate-900 text-slate-100"
          : "from-slate-50 via-white to-slate-100 text-slate-900"
      }`}
    >
      <div className="container mx-auto flex min-h-screen items-center justify-center p-6">
        <div className="w-full max-w-4xl">
          {/* Header */}
          <header className="mb-8 text-center relative">
            <h1
              className={`text-4xl font-bold mb-3 ${
                isDark ? "text-slate-100" : "text-slate-900"
              }`}
            >
              {APP_UI_CONFIG.title}
            </h1>
            <p
              className={`text-sm ${
                isDark ? "text-slate-400" : "text-slate-600"
              }`}
            >
              {APP_UI_CONFIG.subtitle}
            </p>
            
            {/* Call Button */}
            {!isInCall && (
              <button
                className={`absolute top-0 right-0 flex items-center gap-2 px-4 py-2 rounded-full transition-all duration-200 ${
                  isDark
                    ? "bg-slate-800 hover:bg-slate-700 text-slate-100 ring-1 ring-slate-700"
                    : "bg-white hover:bg-slate-50 text-slate-900 ring-1 ring-slate-200 shadow-sm"
                }`}
                onClick={onStartCall}
              >
                <span className="text-xl">📞</span>
                <span className="text-sm font-medium">Call</span>
              </button>
            )}
          </header>

          {/* Chat Container */}
          <div
            className={`relative overflow-hidden rounded-3xl shadow-2xl transition-all duration-300 ${
              isDark
                ? "bg-slate-900/70 ring-1 ring-slate-800/60 backdrop-blur"
                : "bg-white/80 ring-1 ring-slate-200/60 backdrop-blur"
            }`}
            style={{ height: "70vh" }}
          >
            {children}
          </div>

          {/* Footer */}
          <footer
            className={`mt-6 text-center text-xs ${
              isDark ? "text-slate-500" : "text-slate-500"
            }`}
          >
            {APP_UI_CONFIG.footer}
          </footer>
        </div>
      </div>
    </div>
  );
}


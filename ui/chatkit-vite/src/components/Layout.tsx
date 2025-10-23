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
        </div>
      </div>
    </div>
  );
}


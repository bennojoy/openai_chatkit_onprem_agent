import { useCallback, useEffect, useState } from "react";
import { THEME_CONFIG } from "../lib/config";

export type ColorScheme = "light" | "dark";

function getInitialScheme(): ColorScheme {
  if (typeof window === "undefined") {
    return "light";
  }

  // Check localStorage first
  const stored = window.localStorage.getItem(THEME_CONFIG.storageKey) as ColorScheme | null;
  if (stored === "light" || stored === "dark") {
    return stored;
  }

  // Fall back to system preference
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

export function useColorScheme() {
  const [scheme, setScheme] = useState<ColorScheme>(getInitialScheme);

  useEffect(() => {
    if (typeof document === "undefined") return;

    const root = document.documentElement;
    
    // Apply or remove dark class
    if (scheme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }

    // Persist to localStorage
    window.localStorage.setItem(THEME_CONFIG.storageKey, scheme);
  }, [scheme]);

  const toggle = useCallback(() => {
    setScheme((current) => (current === "dark" ? "light" : "dark"));
  }, []);

  const setExplicit = useCallback((value: ColorScheme) => {
    setScheme(value);
  }, []);

  return {
    scheme,
    toggle,
    setScheme: setExplicit,
  };
}


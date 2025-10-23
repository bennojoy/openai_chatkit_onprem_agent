// Shared TypeScript types

export type ColorScheme = "light" | "dark";

export type SessionRequest = {
  user: string;
};

export type SessionResponse = {
  client_secret: string;
};


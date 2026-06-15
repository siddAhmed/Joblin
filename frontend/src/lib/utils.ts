import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "Never";
  // Backend stores datetimes as naive UTC strings (SQLite strips tz info).
  // JS parses ISO strings without a timezone designator as local time, not UTC.
  // Append Z so the browser correctly converts UTC → local for display.
  const utcStr = iso.endsWith("Z") || /[+-]\d{2}:?\d{2}$/.test(iso) ? iso : iso + "Z";
  return new Date(utcStr).toLocaleString();
}

export function formatScore(score: number): string {
  return (score * 100).toFixed(0) + "%";
}

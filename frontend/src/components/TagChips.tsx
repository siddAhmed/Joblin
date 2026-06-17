import { useState } from "react";

export interface TagChipsProps {
  value: string[];
  onChange: (v: string[]) => void;
  suggestions?: string[];
  color?: "blue" | "red";
}

const ACTIVE: Record<"blue" | "red", string> = {
  blue: "border-[#4e9eff] bg-[#0e2040] text-[#4e9eff]",
  red: "border-[#4a1a1a] bg-[#1a0a0a] text-[#f87171]",
};
const INACTIVE = "border-[#2a2a2a] border-dashed text-[#555] bg-transparent";

export function TagChips({ value, onChange, suggestions = [], color = "blue" }: TagChipsProps) {
  const [adding, setAdding] = useState(false);
  const [input, setInput] = useState("");

  const remove = (tag: string) => onChange(value.filter((v) => v !== tag));

  const add = (tag: string) => {
    const t = tag.trim();
    if (t && !value.includes(t)) onChange([...value, t]);
  };

  const toggle = (tag: string) =>
    value.includes(tag) ? remove(tag) : add(tag);

  const commit = () => {
    input.split(",").map((s) => s.trim()).filter(Boolean).forEach(add);
    setInput("");
    setAdding(false);
  };

  const inactive = suggestions.filter((s) => !value.includes(s));

  return (
    <div className="flex flex-wrap gap-1.5">
      {value.map((tag) => (
        <button
          key={tag}
          type="button"
          onClick={() => remove(tag)}
          className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${ACTIVE[color]}`}
        >
          {tag} ✕
        </button>
      ))}
      {inactive.map((tag) => (
        <button
          key={tag}
          type="button"
          onClick={() => toggle(tag)}
          className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${INACTIVE}`}
        >
          {tag}
        </button>
      ))}
      {adding ? (
        <input
          autoFocus
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") { e.preventDefault(); commit(); }
            if (e.key === "Escape") { setInput(""); setAdding(false); }
          }}
          onBlur={commit}
          placeholder="type and press Enter"
          className="text-[11px] px-2.5 py-1 rounded-full border border-[#2a2a2a] bg-transparent text-[#e5e5e5] outline-none w-36"
        />
      ) : (
        <button
          type="button"
          onClick={() => setAdding(true)}
          className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${INACTIVE}`}
        >
          + Add
        </button>
      )}
    </div>
  );
}

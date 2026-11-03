"use client";

import { nextTab } from "@/lib/route-state";

/** Tabs with the WAI-ARIA keyboard pattern: arrows, Home and End move and select, and only the selected tab is in the Tab order. */
export function TabList<T extends string>({
  items,
  label,
  onChange,
  value,
  className,
}: {
  items: readonly (readonly [T, string])[];
  label: string;
  onChange: (id: T) => void;
  value: T;
  className?: string;
}) {
  return (
    <div aria-label={label} className={className} role="tablist">
      {items.map(([id, name], i) => (
        <button
          aria-selected={value === id}
          className="tab"
          key={id}
          onClick={() => onChange(id)}
          onKeyDown={(e) => {
            const to = nextTab(e.key, i, items.length);
            if (to === null) return;
            e.preventDefault();
            onChange(items[to][0]);
            (e.currentTarget.parentElement?.querySelectorAll<HTMLElement>('[role="tab"]')[to])?.focus();
          }}
          role="tab"
          tabIndex={value === id ? 0 : -1}
          type="button"
        >
          {name}
        </button>
      ))}
    </div>
  );
}

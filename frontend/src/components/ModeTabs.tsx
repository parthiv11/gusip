import { KeyboardEvent } from "react";

export type ModeOption<T extends string> = {
  id: T;
  label: string;
  hint?: string;
};

export default function ModeTabs<T extends string>({
  label,
  value,
  options,
  onChange,
  idPrefix,
}: {
  label: string;
  value: T;
  options: ModeOption<T>[];
  onChange: (id: T) => void;
  idPrefix: string;
}) {
  const ids = options.map((o) => o.id);

  function select(id: T) {
    onChange(id);
    requestAnimationFrame(() => {
      document.getElementById(`${idPrefix}-${id}`)?.focus();
    });
  }

  function onKey(e: KeyboardEvent<HTMLDivElement>) {
    const i = ids.indexOf(value);
    if (i < 0) return;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      e.preventDefault();
      select(ids[(i + 1) % ids.length]);
    } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      e.preventDefault();
      select(ids[(i - 1 + ids.length) % ids.length]);
    } else if (e.key === "Home") {
      e.preventDefault();
      select(ids[0]);
    } else if (e.key === "End") {
      e.preventDefault();
      select(ids[ids.length - 1]);
    }
  }

  return (
    <div
      role="tablist"
      aria-label={label}
      onKeyDown={onKey}
      className="flex flex-wrap gap-1 rounded border border-white/10 p-0.5 bg-ink-950/60"
    >
      {options.map((opt) => {
        const selected = value === opt.id;
        return (
          <button
            key={opt.id}
            type="button"
            role="tab"
            id={`${idPrefix}-${opt.id}`}
            aria-selected={selected}
            aria-controls={`${idPrefix}-panel`}
            tabIndex={selected ? 0 : -1}
            title={opt.hint}
            onClick={() => select(opt.id)}
            className={`px-3 py-1.5 rounded text-xs font-medium whitespace-nowrap min-h-8 ${
              selected
                ? "bg-white/10 text-brass-400"
                : "text-slate-300 hover:text-white hover:bg-white/5"
            }`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

import type { ReactNode } from "react";

export function PageHeader({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return (
    <div className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div><p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#5478F5]">{eyebrow}</p><h1 className="mt-2 text-3xl font-semibold tracking-tight text-[#101828]">{title}</h1><p className="mt-2 text-sm leading-6 text-slate-500">{description}</p></div>
      {action}
    </div>
  );
}

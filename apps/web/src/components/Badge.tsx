import type { ReactNode } from "react";

export function Badge({ tone = "slate", children }: { tone?: "blue" | "green" | "amber" | "slate" | "rose"; children: ReactNode }) {
  const styles = {
    blue: "bg-blue-50 text-[#4869df] ring-blue-100",
    green: "bg-emerald-50 text-emerald-700 ring-emerald-100",
    amber: "bg-amber-50 text-amber-700 ring-amber-100",
    slate: "bg-slate-100 text-slate-600 ring-slate-200",
    rose: "bg-rose-50 text-rose-700 ring-rose-100",
  };
  return <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${styles[tone]}`}>{children}</span>;
}

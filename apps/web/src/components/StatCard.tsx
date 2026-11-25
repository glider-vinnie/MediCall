import type { LucideIcon } from "lucide-react";

export function StatCard({ label, value, detail, icon: Icon, accent = "blue" }: { label: string; value: string | number; detail: string; icon: LucideIcon; accent?: "blue" | "green" | "navy" | "amber" }) {
  const color = { blue: "bg-blue-50 text-[#5478F5]", green: "bg-emerald-50 text-emerald-600", navy: "bg-slate-100 text-[#101828]", amber: "bg-amber-50 text-amber-600" };
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_5px_16px_rgba(16,24,40,0.045)] transition-all duration-200 ease-out hover:-translate-y-0.5 hover:shadow-[0_10px_24px_rgba(16,24,40,0.085)]">
      <div className="flex items-start justify-between"><div><p className="text-sm font-medium text-slate-500">{label}</p><p className="mt-3 text-3xl font-semibold tracking-tight text-[#101828]">{value}</p></div><div className={`rounded-xl p-2.5 ${color[accent]}`}><Icon size={20} /></div></div>
      <p className="mt-4 text-xs text-slate-500">{detail}</p>
    </article>
  );
}

import type { LucideIcon } from "lucide-react";

export function EmptyState({ icon: Icon, title, detail }: { icon: LucideIcon; title: string; detail: string }) {
  return (
    <div className="flex min-h-52 flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-white px-6 text-center">
      <div className="mb-3 rounded-xl bg-slate-50 p-3 text-slate-400"><Icon size={22} /></div>
      <p className="font-semibold text-[#101828]">{title}</p>
      <p className="mt-1 max-w-sm text-sm leading-6 text-slate-500">{detail}</p>
    </div>
  );
}

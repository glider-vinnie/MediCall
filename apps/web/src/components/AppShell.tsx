import { Activity, CalendarDays, LayoutDashboard, Menu, Stethoscope, X } from "lucide-react";
import type { ReactNode } from "react";

export type PageId = "overview" | "doctors" | "appointments" | "availability" | "receptionist";

const navigation: { id: PageId; label: string; icon: typeof LayoutDashboard }[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "doctors", label: "Doctors", icon: Stethoscope },
  { id: "appointments", label: "Appointments", icon: CalendarDays },
  { id: "availability", label: "Availability", icon: Activity },
];

export function AppShell({ activePage, onNavigate, children, mobileOpen, onToggleMobile }: { activePage: PageId; onNavigate: (page: PageId) => void; children: ReactNode; mobileOpen: boolean; onToggleMobile: () => void }) {
  const navigate = (page: PageId) => { onNavigate(page); if (mobileOpen) onToggleMobile(); };
  return (
    <div className="min-h-screen bg-[#F7F8FA] text-slate-700">
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-[#E8ECF2] bg-white px-4 py-6 text-slate-700 shadow-[8px_0_24px_rgba(16,24,40,0.025)] transition-transform duration-300 ease-out lg:translate-x-0 ${mobileOpen ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex items-center justify-between px-3"><button onClick={() => navigate("overview")} className="flex items-center gap-3 text-left"><span className="grid size-10 place-items-center rounded-xl bg-[#5478F5] text-white shadow-[0_5px_12px_rgba(84,120,245,0.24)]"><Activity size={21} /></span><span><strong className="block text-base tracking-tight text-[#101828]">MediCall</strong><span className="text-xs text-slate-500">Care operations</span></span></button><button onClick={onToggleMobile} className="rounded-lg p-2 text-slate-500 transition hover:bg-slate-100 hover:text-[#101828] lg:hidden"><X size={20} /></button></div>
        <nav className="mt-10 space-y-1">
          {navigation.map(({ id, label, icon: Icon }) => <button key={id} onClick={() => navigate(id)} className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium transition-all duration-200 ease-out ${activePage === id ? "bg-[#EEF2FF] text-[#5478F5] shadow-[0_2px_8px_rgba(84,120,245,0.08)]" : "text-slate-500 hover:bg-slate-50 hover:text-[#101828]"}`}><Icon size={18} />{label}</button>)}
        </nav>
        <div className={`mt-auto rounded-2xl border border-[#DCE5FF] bg-[#EEF2FF] p-4 shadow-[0_6px_18px_rgba(16,24,40,0.05)] transition-all duration-200 ${activePage === "receptionist" ? "receptionist-card-enter" : ""}`}><p className="text-xs font-semibold uppercase tracking-wider text-[#5478F5]">AI receptionist</p><p className="mt-2 text-sm leading-5 text-slate-600">Voice experience is available as a product preview.</p><button onClick={() => navigate("receptionist")} className="mt-3 text-sm font-semibold text-[#4869DF] transition-colors hover:text-[#101828]">Open preview →</button></div>
      </aside>
      {mobileOpen && <button aria-label="Close menu overlay" onClick={onToggleMobile} className="fixed inset-0 z-30 bg-slate-950/35 lg:hidden" />}
      <div className="lg:pl-72"><header className="sticky top-0 z-20 flex h-20 items-center justify-between border-b border-slate-200 bg-[#F7F8FA]/95 px-5 backdrop-blur sm:px-8"><button onClick={onToggleMobile} className="rounded-xl border border-slate-200 bg-white p-2 text-slate-600 shadow-sm transition hover:bg-slate-50 lg:hidden"><Menu size={20} /></button><div className="hidden sm:block"><p className="text-sm font-medium text-[#101828]">MediCall Clinic</p><p className="text-xs text-slate-500">Appointment operations</p></div><button onClick={() => navigate("receptionist")} className="rounded-xl bg-[#101828] px-4 py-2.5 text-sm font-semibold text-white shadow-[0_4px_12px_rgba(16,24,40,0.12)] transition-all duration-200 hover:-translate-y-0.5 hover:bg-slate-800 hover:shadow-[0_7px_16px_rgba(16,24,40,0.15)]">Receptionist preview</button></header><main className="mx-auto max-w-[1500px] p-5 sm:p-8">{children}</main></div>
    </div>
  );
}

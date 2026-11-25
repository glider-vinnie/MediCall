import { Bot, CalendarCheck2, CalendarX2, Clock3, Stethoscope } from "lucide-react";

import { Badge } from "../components/Badge";
import { EmptyState } from "../components/EmptyState";
import { StatCard } from "../components/StatCard";
import { formatDate, formatTime, initials } from "../lib/format";
import type { DashboardData } from "../types/api";
import { PageHeader } from "./PageHeader";

export function OverviewPage({ data }: { data: DashboardData }) {
  const booked = data.appointments.filter((appointment) => appointment.status === "booked");
  const cancelled = data.appointments.filter((appointment) => appointment.status === "cancelled");
  const activeDoctors = new Set(data.slots.filter((slot) => slot.status === "available").map((slot) => slot.doctor_id)).size;
  const activity = [...data.appointments].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 5);
  return (
    <>
      <PageHeader eyebrow="Operations at a glance" title="Good morning, clinic team." description="A clear view of schedules, patient flow, and the assistant surface." />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Total doctors" value={data.doctors.length} detail="Across 6 clinical specialties" icon={Stethoscope} accent="blue" />
        <StatCard label="Available slots" value={data.slots.filter((slot) => slot.status === "available").length} detail="Open future consultation times" icon={Clock3} accent="green" />
        <StatCard label="Booked appointments" value={booked.length} detail="Confirmed in the schedule" icon={CalendarCheck2} accent="navy" />
        <StatCard label="Cancelled" value={cancelled.length} detail="Released back to availability" icon={CalendarX2} accent="amber" />
      </div>
      <div className="mt-6 grid gap-6 xl:grid-cols-[1.2fr_.8fr]">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_6px_18px_rgba(16,24,40,0.045)] sm:p-6">
          <div className="mb-5 flex items-center justify-between"><div><h2 className="font-semibold text-[#101828]">Recent activity</h2><p className="mt-1 text-sm text-slate-500">Latest schedule records from the appointment service.</p></div><Badge tone="slate">{data.source === "live" ? "Live data" : "Demo data"}</Badge></div>
          {activity.length === 0 ? <EmptyState icon={CalendarCheck2} title="No activity yet" detail="New voice-assisted bookings will appear here after the future call pipeline is connected." /> : <div className="divide-y divide-slate-100">{activity.map((appointment) => <div key={appointment.id} className="flex items-center gap-3 py-4"><span className="grid size-10 shrink-0 place-items-center rounded-full bg-[#EEF2FF] text-xs font-bold text-[#5478F5]">{initials(appointment.doctor.name)}</span><div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-[#101828]">{appointment.patient_name ?? "Caller appointment"}</p><p className="mt-0.5 truncate text-xs text-slate-500">{appointment.doctor.name} · {formatDate(appointment.appointment_date)} at {formatTime(appointment.start_time)}</p></div><Badge tone={appointment.status === "booked" ? "green" : "rose"}>{appointment.status === "booked" ? "Booked" : "Cancelled"}</Badge></div>)}</div>}
        </section>
        <div className="space-y-6">
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_6px_18px_rgba(16,24,40,0.045)] sm:p-6"><div className="flex items-start justify-between"><div><h2 className="font-semibold text-[#101828]">Doctor availability</h2><p className="mt-1 text-sm text-slate-500">Open schedules for upcoming care.</p></div><span className="grid size-9 place-items-center rounded-xl bg-emerald-50 text-emerald-600"><Stethoscope size={18} /></span></div><div className="mt-5 space-y-3">{data.doctors.slice(0, 4).map((doctor) => { const count = data.slots.filter((slot) => slot.doctor_id === doctor.id && slot.status === "available").length; return <div key={doctor.id} className="flex items-center justify-between gap-3"><div><p className="text-sm font-medium text-[#101828]">{doctor.name}</p><p className="text-xs text-slate-500">{doctor.specialty}</p></div><span className="text-sm font-semibold text-emerald-700">{count} open</span></div>; })}</div><p className="mt-5 text-xs text-slate-500">{activeDoctors} clinicians have open future slots.</p></section>
          <section className="rounded-2xl border border-[#5478F5]/20 bg-[#EEF2FF] p-5 shadow-[0_6px_18px_rgba(84,120,245,0.07)]"><div className="flex gap-3"><span className="grid size-10 shrink-0 place-items-center rounded-xl bg-[#5478F5] text-white shadow-[0_5px_12px_rgba(84,120,245,0.22)]"><Bot size={20} /></span><div><div className="flex flex-wrap items-center gap-2"><h2 className="font-semibold text-[#101828]">AI receptionist</h2><Badge tone="amber">Preview only</Badge></div><p className="mt-2 text-sm leading-6 text-slate-600">The call experience is designed and ready to review. Voice connection and transcripts are not active in this milestone.</p></div></div></section>
        </div>
      </div>
    </>
  );
}

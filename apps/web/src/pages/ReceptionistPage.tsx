import { AudioLines, Mic, MicOff, Phone, PhoneOff, ShieldCheck, Volume2, Waves } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "../components/Badge";
import { useVoiceCall } from "../hooks/useVoiceCall";
import { PageHeader } from "./PageHeader";

const durationLabel = (seconds: number) => `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;

export function ReceptionistPage({ onAppointmentChange }: { onAppointmentChange?: () => void }) {
  const voice = useVoiceCall(onAppointmentChange);
  const [seconds, setSeconds] = useState(0);
  const active = voice.status === "connected" || voice.status === "connecting";

  useEffect(() => {
    if (voice.status !== "connected") { setSeconds(0); return; }
    const timer = window.setInterval(() => setSeconds((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [voice.status]);

  const badge = voice.status === "connected" ? <Badge tone="green">Live call</Badge>
    : voice.status === "connecting" ? <Badge tone="blue">Connecting</Badge>
      : voice.config?.configured ? <Badge tone="slate">Ready</Badge>
        : <Badge tone="amber">Demo mode · not connected</Badge>;

  return <div className="receptionist-preview-enter">
    <PageHeader eyebrow="Voice experience" title="AI receptionist" description={voice.config?.configured ? "Start a secure browser voice call. Your microphone is requested only after you choose Start call." : "Live providers are not configured. This is a non-interactive demo state, not a simulated AI call."} action={badge} />
    <div className="grid gap-6 xl:grid-cols-[minmax(340px,.78fr)_minmax(360px,1.22fr)]">
      <section className="relative overflow-hidden rounded-[2rem] bg-[#101828] p-5 text-white shadow-[0_12px_30px_rgba(16,24,40,.16)] sm:p-7">
        <div className="absolute -right-14 -top-14 size-52 rounded-full border-[28px] border-[#5478F5]/20" />
        <div className="relative">
          <div className="flex items-center justify-between"><span className="text-sm font-semibold text-slate-300">MediCall line</span><span className={`size-2 rounded-full ${voice.status === "connected" ? "bg-emerald-400" : "bg-amber-400"}`} /></div>
          <div className="mt-10 text-center"><div className="mx-auto grid size-20 place-items-center rounded-[1.6rem] bg-white/10 text-blue-300"><AudioLines size={34} /></div><p className="mt-5 text-xl font-semibold">Caller identity</p><p className="mt-1 text-sm text-slate-400">Available only after a verified spoken phone number.</p><div className="mt-5 inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1.5 text-xs font-medium text-slate-300"><ShieldCheck size={14} /> {voice.status === "connected" ? "Live session · verification required" : "No active call"}</div></div>
          <div className="mt-9 rounded-2xl border border-white/10 bg-white/5 p-4"><div className="flex items-center justify-between text-sm"><span className="text-slate-400">Call duration</span><span className="font-mono text-lg font-semibold text-white">{durationLabel(seconds)}</span></div><div className="mt-5 flex h-14 items-center justify-center gap-1.5" aria-label={voice.status === "connected" ? "Live audio transport connected" : "Audio transport inactive"}>{Array.from({ length: 18 }, (_, index) => <span key={index} style={{ height: voice.status === "connected" ? 12 + ((index * 11) % 28) : 8 }} className={`w-1.5 rounded-full ${voice.status === "connected" ? "animate-pulse bg-[#5478F5]" : "bg-[#5478F5]/40"}`} />)}</div><p className="mt-3 text-center text-xs text-slate-400">{voice.connectionDetail ?? (voice.status === "connected" ? "Live WebRTC audio is connected." : "No microphone is active.")}</p></div>
          <div className="mt-8 flex justify-center gap-4">{!active ? <button onClick={() => void voice.start()} disabled={!voice.config?.configured} aria-label="Start voice call" className="inline-flex h-14 items-center gap-2 rounded-full bg-[#5478F5] px-6 text-sm font-semibold text-white shadow-lg shadow-blue-950/25 transition hover:bg-[#4469e9] disabled:cursor-not-allowed disabled:bg-white/15 disabled:text-slate-400"><Phone size={19} /> Start call</button> : <><button onClick={voice.toggleMute} aria-label={voice.muted ? "Unmute microphone" : "Mute microphone"} className="grid size-14 place-items-center rounded-full bg-white/10 text-white transition hover:bg-white/20">{voice.muted ? <MicOff size={21} /> : <Mic size={21} />}</button><button onClick={() => void voice.end()} aria-label="End call" className="grid size-14 place-items-center rounded-full bg-rose-500 text-white transition hover:bg-rose-400"><PhoneOff size={21} /></button><span className="grid size-14 place-items-center rounded-full bg-white/10 text-slate-300"><Volume2 size={21} /></span></>}</div>
          {voice.error && <p role="alert" className="mt-5 rounded-xl border border-rose-300/25 bg-rose-500/10 px-3 py-2 text-center text-xs leading-5 text-rose-100">{voice.error}</p>}
        </div>
      </section>
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_6px_18px_rgba(16,24,40,0.05)] sm:p-7"><div className="flex items-start justify-between gap-4"><div><h2 className="font-semibold text-[#101828]">Conversation transcript</h2><p className="mt-1 text-sm leading-6 text-slate-500">Only real speech transcribed by the live provider appears here.</p></div><Waves className="text-[#5478F5]" size={22} /></div>
        <div className="mt-7 min-h-72 space-y-3 rounded-2xl border border-dashed border-slate-200 bg-[#F7F8FA] p-4">{voice.transcripts.length ? voice.transcripts.map((item) => <div key={item.id} className={`max-w-[88%] rounded-2xl px-4 py-3 text-sm leading-6 ${item.role === "user" ? "ml-auto bg-[#EEF2FF] text-[#284bbf]" : "bg-white text-slate-700 shadow-sm"}`}><span className="mb-1 block text-[11px] font-bold uppercase tracking-[.12em] text-slate-400">{item.role === "user" ? "Caller" : "MediCall"}</span>{item.text}</div>) : <div className="flex min-h-64 flex-col items-center justify-center px-6 text-center"><div className="grid size-12 place-items-center rounded-2xl bg-white text-[#5478F5] shadow-[0_3px_10px_rgba(16,24,40,0.06)]"><AudioLines size={22} /></div><h3 className="mt-4 font-semibold text-[#101828]">No transcript yet</h3><p className="mt-2 max-w-sm text-sm leading-6 text-slate-500">{voice.config?.configured ? "Start a call and speak to the assistant. No transcript is created until live speech is received." : "This dashboard does not fabricate a conversation while live provider configuration is unavailable."}</p></div>}</div>
        {(voice.toolStatus || voice.confirmation) && <div className="mt-5 rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm leading-6 text-blue-900">{voice.confirmation ?? voice.toolStatus}</div>}
      </section>
    </div>
  </div>;
}

import { AlertCircle, DatabaseZap, RotateCw } from "lucide-react";

export function StatusBanner({ source, error, onRetry }: { source: "live" | "mock"; error: string | null; onRetry: () => void }) {
  if (source === "live") return null;
  return (
    <div className="mb-6 flex flex-wrap items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      <DatabaseZap size={18} className="shrink-0" />
      <span><strong>Demo data only.</strong> The local backend is unavailable{error ? ` (${error})` : ""}.</span>
      <button onClick={onRetry} className="ml-auto inline-flex items-center gap-1 font-semibold text-amber-900 hover:text-amber-700"><RotateCw size={15} /> Retry</button>
    </div>
  );
}

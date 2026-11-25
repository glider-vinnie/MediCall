export function LoadingState({ label = "Loading dashboard data" }: { label?: string }) {
  return (
    <div className="flex min-h-64 flex-col items-center justify-center gap-3 text-sm text-slate-500">
      <span className="size-8 animate-spin rounded-full border-2 border-[#5478F5]/20 border-t-[#5478F5]" />
      {label}
    </div>
  );
}

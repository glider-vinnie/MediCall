import { useCallback, useEffect, useState } from "react";

import { api } from "../lib/api";
import { mockDashboardData } from "../lib/mock";
import type { DashboardData } from "../types/api";

interface DashboardState {
  data: DashboardData | null;
  isLoading: boolean;
  error: string | null;
}

export function useDashboardData() {
  const [state, setState] = useState<DashboardState>({ data: null, isLoading: true, error: null });

  const refresh = useCallback(async (signal?: AbortSignal) => {
    setState((current) => ({ ...current, isLoading: true, error: null }));
    try {
      const [health, doctors, slots, appointments] = await Promise.all([
        api.health(signal),
        api.doctors(signal),
        api.slots(signal),
        api.appointments(signal),
      ]);
      setState({ data: { health, doctors, slots, appointments, source: "live" }, isLoading: false, error: null });
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      const message = error instanceof Error ? error.message : "The backend could not be reached.";
      setState({ data: mockDashboardData, isLoading: false, error: message });
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void refresh(controller.signal);
    return () => controller.abort();
  }, [refresh]);

  return { ...state, refresh: () => refresh() };
}

import { useState } from "react";

import { AppShell, type PageId } from "./components/AppShell";
import { LoadingState } from "./components/LoadingState";
import { StatusBanner } from "./components/StatusBanner";
import { useDashboardData } from "./hooks/useDashboardData";
import { AppointmentsPage } from "./pages/AppointmentsPage";
import { AvailabilityPage } from "./pages/AvailabilityPage";
import { DoctorsPage } from "./pages/DoctorsPage";
import { OverviewPage } from "./pages/OverviewPage";
import { ReceptionistPage } from "./pages/ReceptionistPage";

export default function App() {
  const [page, setPage] = useState<PageId>("overview");
  const [mobileOpen, setMobileOpen] = useState(false);
  const { data, isLoading, error, refresh } = useDashboardData();
  const content = () => {
    if (isLoading && !data) return <LoadingState />;
    if (!data) return <LoadingState label="Preparing dashboard" />;
    switch (page) {
      case "doctors": return <DoctorsPage doctors={data.doctors} />;
      case "appointments": return <AppointmentsPage appointments={data.appointments} doctors={data.doctors} />;
      case "availability": return <AvailabilityPage doctors={data.doctors} slots={data.slots} appointments={data.appointments} />;
      case "receptionist": return <ReceptionistPage onAppointmentChange={() => void refresh()} />;
      default: return <OverviewPage data={data} />;
    }
  };
  return <AppShell activePage={page} onNavigate={setPage} mobileOpen={mobileOpen} onToggleMobile={() => setMobileOpen((open) => !open)}>{data && <StatusBanner source={data.source} error={error} onRetry={refresh} />}<div key={page} className="page-enter">{content()}</div></AppShell>;
}

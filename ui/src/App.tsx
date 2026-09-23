import { Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/AppShell";

import OverviewPage from "./pages/Overview";
import DashboardPage from "./pages/Dashboard";
import LeadsPage from "./pages/Leads";
import LeadDetailPage from "./pages/LeadDetail";
import InsightsPage from "./pages/Insights";
import RunPage from "./pages/Run";
import AnalyzePage from "./pages/Analyze";
import HistoryPage from "./pages/History";
import AutomationPage from "./pages/Automation";
import ReportsPage from "./pages/Reports";
import SearchPage from "./pages/Search";
import StoragePage from "./pages/Storage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/overview" element={<OverviewPage />} />
        <Route path="/leads" element={<LeadsPage />} />
        <Route path="/leads/:id" element={<LeadDetailPage />} />
        <Route path="/insights" element={<InsightsPage />} />
        <Route path="/run" element={<RunPage />} />
        <Route path="/analyze" element={<AnalyzePage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/automation" element={<AutomationPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/storage" element={<StoragePage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}

function NotFound() {
  return (
    <div className="page-head">
      <h1>Not found</h1>
      <p className="caption">That tab does not exist in the ecom-intel shell.</p>
    </div>
  );
}
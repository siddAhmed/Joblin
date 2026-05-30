import { useQuery } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { api } from "./api/client";
import { Layout } from "./components/Layout";
import { Dashboard } from "./pages/Dashboard";
import { Matches } from "./pages/Matches";
import { Jobs } from "./pages/Jobs";
import { Companies } from "./pages/Companies";
import { Runs } from "./pages/Runs";
import { RunDetail } from "./pages/RunDetail";
import { Settings } from "./pages/Settings";
import { Onboarding } from "./pages/Onboarding";
import { Usage } from "./pages/Usage";
import { Insights } from "./pages/Insights";

function AppInner() {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["onboarding-status"],
    queryFn: () => api.get("/onboarding-status").then((r) => r.data as { needs_onboarding: boolean }),
  });

  if (isLoading) return null;
  if (data?.needs_onboarding) return <Onboarding onComplete={() => refetch()} />;

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/matches" element={<Matches />} />
        <Route path="/jobs" element={<Jobs />} />
        <Route path="/companies" element={<Companies />} />
        <Route path="/runs" element={<Runs />} />
        <Route path="/runs/:id" element={<RunDetail />} />
        <Route path="/usage" element={<Usage />} />
        <Route path="/insights" element={<Insights />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppInner />
    </BrowserRouter>
  );
}

import { useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router";
import {
  Activity,
  Box,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Cpu,
  FileText,
  LayoutDashboard,
  Menu,
  Moon,
  RefreshCw,
  Server,
  Settings as SettingsIcon,
  Sun,
  Terminal,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useApi } from "./lib/api";
import type { Overview } from "./lib/types";
import { time } from "./lib/utils";
import { Status } from "./components/common";
import { Button } from "./components/ui/button";
import { NodesPage, NodeDetailsPage } from "./pages/Nodes";
import { RayPage } from "./pages/Ray";
import { MetricsPage } from "./pages/Metrics";
import { LogsPage } from "./pages/Logs";
import { SettingsPage } from "./pages/Settings";
import { JobsPage } from "./pages/Jobs";
import { OverviewPage } from "./pages/Overview";
const navigation = [
  ["overview", "Overview", LayoutDashboard],
  ["nodes", "Nodes", Server],
  ["ray", "Ray Cluster", Box],
  ["jobs", "Jobs", Terminal],
  ["metrics", "Metrics", Activity],
  ["logs", "Logs", FileText],
  ["settings", "Settings", SettingsIcon],
] as const;
export default function App() {
  const [collapsed, setCollapsed] = useState(false),
    [mobile, setMobile] = useState(false);
  const [light, setLight] = useState(
    () => localStorage.getItem("arc-theme") === "light",
  );
  const query = useQueryClient(),
    location = useLocation(),
    overview = useApi<Overview>("/cluster/overview");
  const current =
    navigation.find(([path]) =>
      location.pathname.startsWith(`/${path}`),
    )?.[1] ?? "Overview";
  return (
    <div
      className={`app ${collapsed ? "collapsed" : ""} ${light ? "light" : ""} ${mobile ? "mobile-open" : ""}`}
    >
      <aside className="sidebar">
        <NavLink to="/overview" className="brand" aria-label="ARC overview">
          <svg viewBox="0 0 30 30" width="28" height="28" fill="none">
            <path
              d="M3 25 15 4l12 21H3Z"
              stroke="currentColor"
              strokeWidth="2"
            />
            <path d="m10 25 5-9 5 9" stroke="currentColor" strokeWidth="2" />
          </svg>
          <b>ARC</b>
          <span className="version">v0.1</span>
        </NavLink>
        <div className="workspace">
          <span className="workspace-mark">A</span>
          <span>
            Personal infrastructure<small>Distributed compute</small>
          </span>
        </div>
        <div className="nav-label">CONTROL PLANE</div>
        <nav aria-label="Main navigation">
          {navigation.map(([path, label, Icon]) => (
            <NavLink
              key={path}
              to={`/${path}`}
              title={label}
              onClick={() => setMobile(false)}
            >
              <Icon size={17} />
              <span>{label}</span>
              {path === "nodes" && <small>5</small>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="private-note">
            <span className="dot" />
            Private network<span className="mono">Tailscale</span>
          </div>
          <a href="/docs" target="_blank" rel="noreferrer">
            <CircleHelp size={16} />
            <span>API documentation</span>
          </a>
          <Button
            variant="ghost"
            onClick={() => setCollapsed(!collapsed)}
            aria-label="Toggle sidebar"
          >
            {collapsed ? (
              <ChevronRight size={16} />
            ) : (
              <>
                <ChevronLeft size={16} />
                <span>Collapse sidebar</span>
              </>
            )}
          </Button>
        </div>
      </aside>
      <div className="app-body">
        <header className="topbar">
          <div className="breadcrumb">
            <Button
              className="mobile-menu"
              size="icon"
              onClick={() => setMobile(!mobile)}
              aria-label="Open navigation"
            >
              <Menu size={17} />
            </Button>
            <Cpu size={16} />
            <span>ARC</span>
            <span className="slash">/</span>
            <strong>{current}</strong>
          </div>
          <div className="header-actions">
            <Status
              value={
                overview.isError
                  ? "unavailable"
                  : (overview.data?.status ?? "unknown")
              }
            />
            <span className="last-refresh mono">
              {time(overview.data?.updated_at)}
            </span>
            <Button
              size="icon"
              onClick={() => void query.invalidateQueries()}
              aria-label="Refresh dashboard"
            >
              <RefreshCw
                size={15}
                className={overview.isFetching ? "spinning" : ""}
              />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              aria-label="Toggle theme"
              onClick={() => {
                setLight(!light);
                localStorage.setItem("arc-theme", !light ? "light" : "dark");
              }}
            >
              {light ? <Moon size={17} /> : <Sun size={17} />}
            </Button>
          </div>
        </header>
        <main>
          <Routes>
            <Route path="/" element={<Navigate to="/overview" replace />} />
            <Route path="/overview" element={<OverviewPage />} />
            <Route path="/nodes" element={<NodesPage />} />
            <Route path="/nodes/:nodeId" element={<NodeDetailsPage />} />
            <Route path="/ray" element={<RayPage />} />
            <Route path="/metrics" element={<MetricsPage />} />
            <Route path="/jobs" element={<JobsPage />} />
            <Route path="/logs" element={<LogsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route
              path="*"
              element={
                <div className="empty">
                  <h1>Page not found</h1>
                  <NavLink to="/overview">Return to overview</NavLink>
                </div>
              }
            />
          </Routes>
        </main>
        <footer>
          <span>
            ARC <span className="muted">/</span> Distributed Compute Control
            Plane
          </span>
          <span>One control plane. Every node.</span>
        </footer>
      </div>
    </div>
  );
}

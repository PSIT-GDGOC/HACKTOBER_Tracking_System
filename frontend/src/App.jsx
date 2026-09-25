import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import React from "react";
import { AuthProvider, RequireRole } from "@/lib/auth";
import { AppShell } from "@/components/Layout";
import { ErrorBoundary } from "@/pages/misc";
import Landing from "@/pages/Landing";
import { AuthWizard, Login } from "@/pages/auth";
import StudentDashboard from "@/pages/student";
import IssueExplorer from "@/pages/issues";
import { Repositories, PullRequests, Commits } from "@/pages/repos";
import { Leaderboard } from "@/pages/engage";
import Profile from "@/pages/profile";
import MaintainerReview from "@/pages/maintainer";
import AdminConsole from "@/pages/admin";
import { Forbidden, NotFound } from "@/pages/misc";

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <HashRouter>
          <Routes>
            {/* ---------- public ---------- */}
            <Route path="/" element={<Landing />} />
            <Route path="/join" element={<AuthWizard />} />
            <Route path="/login" element={<Login />} />

            {/* ---------- authenticated app (sidebar shell + role guard) ---------- */}
            <Route
              path="/dashboard"
              element={
                <RequireRole>
                  <AppShell />
                </RequireRole>
              }
            >
              <Route index element={<StudentDashboard />} />
              <Route path="issues" element={<IssueExplorer />} />
              <Route path="repos" element={<Repositories />} />
              <Route path="repos/:repoId" element={<Repositories />} />
              <Route path="pulls" element={<PullRequests />} />
              <Route path="commits" element={<Commits />} />
              <Route path="leaderboard" element={<Leaderboard />} />
              <Route path="profile" element={<Profile />} />
              <Route path="profile/:userId" element={<Profile />} />

              {/* maintainer + admin */}
              <Route
                path="maintainer"
                element={
                  <RequireRole roles={["maintainer", "admin"]}>
                    <MaintainerReview />
                  </RequireRole>
                }
              />
              <Route
                path="admin"
                element={
                  <RequireRole roles={["admin"]}>
                    <AdminConsole />
                  </RequireRole>
                }
              />

              <Route path="403" element={<Forbidden />} />
              <Route path="*" element={<NotFound />} />
            </Route>

            {/* top-level fallthroughs for legacy links */}
            <Route path="/issues" element={<Navigate to="/dashboard/issues" replace />} />
            <Route path="/pulls" element={<Navigate to="/dashboard/pulls" replace />} />
            <Route path="/commits" element={<Navigate to="/dashboard/commits" replace />} />
            <Route path="/leaderboard" element={<Navigate to="/dashboard/leaderboard" replace />} />
            <Route path="/profile" element={<Navigate to="/dashboard/profile" replace />} />
            <Route path="/signup" element={<Navigate to="/join" replace />} />
            <Route path="/gate" element={<Navigate to="/join" replace />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </HashRouter>
      </AuthProvider>
    </ErrorBoundary>
  );
}

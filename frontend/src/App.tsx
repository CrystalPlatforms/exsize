import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider, useAuth } from "@/auth";
import AppLayout from "@/layouts/AppLayout";
import FamilyPage from "@/pages/FamilyPage";
import TasksPage from "@/pages/TasksPage";
import ExBucksPage from "@/pages/ExBucksPage";
import ShopPage from "@/pages/ShopPage";
import ProfilePage from "@/pages/ProfilePage";
import DashboardPage from "@/pages/DashboardPage";
import SettingsPage from "@/pages/SettingsPage";
import AdminSettingsPage from "@/pages/AdminSettingsPage";
import LeaderboardPage from "@/pages/LeaderboardPage";
import SizePassPage from "@/pages/SizePassPage";
import AvatarItemsPage from "@/pages/AvatarItemsPage";
import TodoPage from "@/pages/TodoPage";
import AuthModal from "@/components/AuthModal";

const queryClient = new QueryClient();

function AppRoutes() {
  const { user, isAuthenticated } = useAuth();

  if (!isAuthenticated || !user) {
    return <AuthModal />;
  }

  return (
    <AppLayout user={user}>
      <Routes>
        <Route path="/dashboard" element={<DashboardPage user={user} />} />
        <Route path="/tasks" element={<TasksPage user={user} />} />
        <Route path="/todo" element={<TodoPage />} />
        <Route path="/family" element={<FamilyPage user={user} />} />
        <Route path="/exbucks" element={<ExBucksPage user={user} />} />
        <Route path="/shop" element={<ShopPage user={user} />} />
        <Route path="/profile" element={<ProfilePage user={user} />} />
        <Route path="/profile/:childId" element={<ProfilePage user={user} />} />
        <Route path="/admin-settings" element={<AdminSettingsPage user={user} />} />
        <Route path="/avatar-items" element={<AvatarItemsPage user={user} />} />
        <Route path="/leaderboard" element={<LeaderboardPage user={user} />} />
        <Route path="/sizepass" element={<SizePassPage user={user} />} />
        <Route path="/settings" element={<SettingsPage user={user} />} />
        <Route
          path="*"
          element={
            <Navigate
              to={user.role === "child" ? "/tasks" : "/dashboard"}
              replace
            />
          }
        />
      </Routes>
    </AppLayout>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

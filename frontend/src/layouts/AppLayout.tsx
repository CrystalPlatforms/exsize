import { type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getBalance, getGamificationProfile, getProfile, type UserResponse } from "@/api";
import { useAuth } from "@/auth";
import { useDarkMode } from "@/hooks/useDarkMode";
import ParentBottomTabBar from "@/components/ParentBottomTabBar";
import ParentTopBar from "@/components/ParentTopBar";
import ChildBottomTabBar from "@/components/ChildBottomTabBar";
import ChildTasksTopBar from "@/components/ChildTasksTopBar";

const SIZEPASS_COLORS = [
  "#ff6b6b", // S - red
  "#ffa502", // i - orange
  "#ffd93d", // z - yellow
  "#6bcb77", // e - green
  "#4d96ff", // P - blue
  "#9b59b6", // a - purple
  "#e84393", // s - pink
  "#00cec9", // s - teal
];

function SizePassButton() {
  const letters = "SizePass".split("");
  return (
    <Link
      to="/sizepass"
      className="sizepass-btn flex items-center rounded-full border-2 border-primary/50 px-3 py-1 text-sm font-bold transition-transform hover:scale-105"
    >
      {letters.map((letter, i) => (
        <span
          key={i}
          className="sizepass-letter"
          style={{
            color: SIZEPASS_COLORS[i],
            animationDelay: `${i * 0.15}s`,
          }}
        >
          {letter}
        </span>
      ))}
    </Link>
  );
}

const NAV_ITEMS: Record<string, { label: string; to: string }[]> = {
  parent: [
    { label: "Dashboard", to: "/dashboard" },
    { label: "Tasks", to: "/tasks" },
    { label: "To-Do", to: "/todo" },
    { label: "Family", to: "/family" },
    { label: "ExBucks", to: "/exbucks" },
    { label: "Settings", to: "/settings" },
  ],
  child: [
    { label: "Tasks", to: "/tasks" },
    { label: "To-Do", to: "/todo" },
    { label: "Family", to: "/family" },
    { label: "ExBucks", to: "/exbucks" },
    { label: "Shop", to: "/shop" },
    { label: "Leaderboard", to: "/leaderboard" },
    { label: "Profile", to: "/profile" },
    { label: "Settings", to: "/settings" },
  ],
  admin: [
    { label: "Dashboard", to: "/dashboard" },
    { label: "Tasks", to: "/tasks" },
    { label: "To-Do", to: "/todo" },
    { label: "Family", to: "/family" },
    { label: "ExBucks", to: "/exbucks" },
    { label: "Avatar Items", to: "/avatar-items" },
    { label: "App Settings", to: "/admin-settings" },
    { label: "Settings", to: "/settings" },
  ],
};

interface AppLayoutProps {
  user: UserResponse;
  children: ReactNode;
}

export default function AppLayout({ user, children }: AppLayoutProps) {
  const { logout } = useAuth();
  const [dark, toggleDark] = useDarkMode();
  const navItems = NAV_ITEMS[user.role] ?? NAV_ITEMS.parent;

  const { data: balanceData } = useQuery({
    queryKey: ["exbucks-balance"],
    queryFn: getBalance,
    retry: false,
    enabled: user.role === "child",
  });

  const { data: profileData } = useQuery({
    queryKey: ["gamification-profile"],
    queryFn: getGamificationProfile,
    retry: false,
    enabled: user.role === "child",
  });

  const { data: fullProfileData } = useQuery({
    queryKey: ["profile"],
    queryFn: getProfile,
    retry: false,
    enabled: user.role === "child",
  });

  return (
    <div className="flex min-h-screen flex-col">
      {user.role === "parent" && <ParentTopBar dark={dark} toggleDark={toggleDark} logout={logout} />}
      {user.role === "child" && fullProfileData && (
        <ChildTasksTopBar
          badges={fullProfileData.badges}
          streak={fullProfileData.streak}
          level={fullProfileData.level}
          exbucksBalance={fullProfileData.exbucks_balance}
        />
      )}
      <header className="border-b bg-background md:block hidden">
        <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4">
          <nav className="flex gap-4">
            {navItems.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className="text-sm font-medium text-muted-foreground hover:text-foreground"
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <SizePassButton />
            {user.role === "child" && profileData != null && (
              <Link
                to="/profile"
                className="flex items-center gap-2 rounded-full border-2 border-primary bg-primary/10 px-4 py-1.5 font-bold text-primary transition-colors hover:bg-primary/20"
                aria-label="Streak"
              >
                <span className="text-2xl">🔥</span>
                <span className="text-lg">{profileData.streak}</span>
              </Link>
            )}
            {user.role === "child" && profileData != null && (
              <Link
                to="/profile"
                className="flex items-center gap-2 rounded-full border-2 border-primary bg-primary/10 px-4 py-1.5 font-bold text-primary transition-colors hover:bg-primary/20"
                aria-label="Level"
              >
                <span className="text-2xl">⭐</span>
                <span className="text-lg">{profileData.level}</span>
              </Link>
            )}
            {user.role === "child" && balanceData != null && (
              <Link
                to="/exbucks"
                className="flex items-center gap-2 rounded-full border-2 border-primary bg-primary/10 px-4 py-1.5 font-bold text-primary transition-colors hover:bg-primary/20"
                aria-label="ExBucks balance"
              >
                <span className="text-2xl">💰</span>
                <span className="text-lg">{balanceData.balance}</span>
              </Link>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={toggleDark}
              aria-label="Toggle dark mode"
            >
              {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
            <Button variant="ghost" size="sm" onClick={logout}>
              Logout
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-6 pb-20 md:pb-6">
        {children}
      </main>
      {user.role === "parent" && <ParentBottomTabBar />}
      {user.role === "child" && <ChildBottomTabBar dark={dark} toggleDark={toggleDark} logout={logout} />}
    </div>
  );
}

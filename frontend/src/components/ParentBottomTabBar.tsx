import { Link, useLocation } from "react-router-dom";
import { LayoutDashboard, Plus, Coins, ClipboardList } from "lucide-react";

const tabs = [
  { label: "Dashboard", to: "/dashboard", icon: LayoutDashboard, prominent: false },
  { label: "Add task", to: "/tasks", icon: Plus, prominent: true },
  { label: "To-Do", to: "/todo", icon: ClipboardList, prominent: false },
  { label: "ExBucks", to: "/exbucks", icon: Coins, prominent: false },
];

export default function ParentBottomTabBar() {
  const { pathname } = useLocation();

  return (
    <nav className="parent-bottom-tab-bar fixed bottom-0 left-0 right-0 z-50 flex items-end justify-around border-t bg-background px-2 pb-[env(safe-area-inset-bottom)] md:hidden">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = pathname === tab.to || pathname.startsWith(tab.to + "/");
        return (
          <Link
            key={tab.to}
            to={tab.to}
            aria-label={tab.label}
            aria-current={isActive ? "page" : undefined}
            className={`tab-item flex flex-col items-center gap-1 px-3 py-2 text-muted-foreground ${tab.prominent ? "prominent-tab -mt-6 rounded-full bg-primary p-4 text-primary-foreground shadow-lg" : ""} ${isActive && !tab.prominent ? "text-foreground font-semibold" : ""}`}
          >
            <Icon className={tab.prominent ? "h-8 w-8" : "h-6 w-6"} />
            <span className="text-xs">{tab.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

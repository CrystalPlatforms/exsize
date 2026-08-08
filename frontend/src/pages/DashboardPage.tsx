import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import Avatar from "@/components/Avatar";
import { getDashboard, getEquippedAvatar, type UserResponse } from "@/api";

interface DashboardPageProps {
  user: UserResponse;
}

function ChildAvatar({ childId }: { childId: number }) {
  const { data } = useQuery({
    queryKey: ["equipped-avatar", childId],
    queryFn: () => getEquippedAvatar(childId),
    retry: false,
  });

  return (
    <Avatar
      icon={data?.icon?.value}
      background={data?.background?.value}
      size="md"
    />
  );
}

export default function DashboardPage({ user: _user }: DashboardPageProps) {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard"],
    queryFn: getDashboard,
    retry: false,
  });

  if (isLoading) return <div>Loading...</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      {data && data.children.length === 0 && (
        <p className="text-muted-foreground">No children in your family yet.</p>
      )}

      {data && data.children.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2" data-testid="children-grid">
          {data.children.map((child) => (
            <Card key={child.id}>
              <CardHeader>
                <div className="flex items-center gap-3">
                  <ChildAvatar childId={child.id} />
                  <CardTitle>{child.email}</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <span className="text-muted-foreground">Tasks completed</span>
                    <p className="text-lg font-semibold">{child.tasks_completed_percent}%</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Streak</span>
                    <p className="text-lg font-semibold">{child.streak}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Earned</span>
                    <p className="text-lg font-semibold">{child.exbucks_earned}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Spent</span>
                    <p className="text-lg font-semibold">{child.exbucks_spent}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {data && data.advanced_stats && (
        <Card>
          <CardHeader>
            <CardTitle>Advanced Stats</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">Total XP Earned</span>
                <p className="text-lg font-semibold">{data.advanced_stats.total_xp_earned}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Best Streak</span>
                <p className="text-lg font-semibold">{data.advanced_stats.best_streak}</p>
              </div>
            </div>
            <div className="space-y-2">
              {data.advanced_stats.children.map((child) => (
                <div key={child.id} className="flex items-center justify-between rounded border p-2">
                  <span className="font-medium">{child.email}</span>
                  <div className="flex gap-3 text-sm">
                    <span>{child.xp} XP</span>
                    <span>Level {child.level}</span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {data && !data.advanced_stats && data.children.length > 0 && (
        <Card className="border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950">
          <CardHeader>
            <CardTitle>Advanced Stats</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Upgrade to SizePass to see XP, levels, and detailed stats per child.
            </p>
            <Link to="/sizepass">
              <Button variant="default">Upgrade to SizePass</Button>
            </Link>
          </CardContent>
        </Card>
      )}

      {data && Object.keys(data.weekly_overview).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Weekly Overview</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {DAYS.map((day) => {
                const entries = data.weekly_overview[day] ?? [];
                return (
                  <div key={day} className="flex flex-col gap-1 sm:flex-row sm:items-start sm:gap-4" data-testid="weekly-day-row">
                    <span className="font-medium sm:w-24 sm:shrink-0">{day}</span>
                    <div className="flex flex-wrap gap-2">
                      {entries.length === 0 ? (
                        <span className="text-sm text-muted-foreground">—</span>
                      ) : (
                        entries.map((entry) => (
                          <span
                            key={entry.child_id}
                            className="rounded bg-muted px-2 py-1 text-sm"
                          >
                            {entry.email}: {entry.approved}/{entry.total}
                          </span>
                        ))
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

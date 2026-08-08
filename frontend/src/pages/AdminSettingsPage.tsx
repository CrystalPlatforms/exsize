import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getAppSettings, updateAppSettings, type UserResponse } from "@/api";

interface AdminSettingsPageProps {
  user: UserResponse;
}

export default function AdminSettingsPage({ user: _user }: AdminSettingsPageProps) {
  const queryClient = useQueryClient();
  const [maxExbucks, setMaxExbucks] = useState("");

  const { data: settings, isLoading } = useQuery({
    queryKey: ["app-settings"],
    queryFn: getAppSettings,
    retry: false,
  });

  useEffect(() => {
    if (settings) {
      setMaxExbucks(String(settings.max_exbucks_per_task));
    }
  }, [settings]);

  const updateMutation = useMutation({
    mutationFn: updateAppSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["app-settings"] });
    },
  });

  if (isLoading) return <div>Loading...</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">App Settings</h1>

      <Card>
        <CardHeader>
          <CardTitle>ExBucks Limits</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              updateMutation.mutate({ max_exbucks_per_task: Number(maxExbucks) });
            }}
          >
            <div>
              <Label htmlFor="max-exbucks">Max ExBucks per Task</Label>
              <Input
                id="max-exbucks"
                type="number"
                value={maxExbucks}
                onChange={(e) => setMaxExbucks(e.target.value)}
              />
            </div>
            <Button type="submit">Save</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

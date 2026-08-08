import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  getSubscription,
  cancelSubscription,
  requestAccountDeletion,
  deleteOwnAccount,
  getProfile,
  setNickname,
  type UserResponse,
} from "@/api";
import { useAuth } from "@/auth";
import { usePushNotifications } from "@/hooks/usePushNotifications";

function NicknameCard({ currentNickname }: { currentNickname: string | null }) {
  const [nickname, setNicknameValue] = useState(currentNickname ?? "");
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (nick: string) => setNickname(nick),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Nickname</CardTitle>
      </CardHeader>
      <CardContent>
        <form
          className="flex flex-col gap-2 sm:flex-row sm:items-end"
          onSubmit={(e) => {
            e.preventDefault();
            if (nickname.trim()) mutation.mutate(nickname.trim());
          }}
        >
          <div className="flex-1">
            <Label htmlFor="nickname">Nickname</Label>
            <Input
              id="nickname"
              value={nickname}
              onChange={(e) => setNicknameValue(e.target.value)}
            />
          </div>
          <Button type="submit" className="min-h-[44px] sm:min-h-0">Save Nickname</Button>
        </form>
      </CardContent>
    </Card>
  );
}

interface SettingsPageProps {
  user: UserResponse;
}

function PushNotificationsCard() {
  const { isSupported, permission, isSubscribed, error, enable, disable } =
    usePushNotifications();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Push Notifications</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {!isSupported ? (
          <p className="text-sm text-muted-foreground">
            Push notifications are not supported on this device.
          </p>
        ) : (
          <>
            <p className="text-sm text-muted-foreground">
              Get reminders for due To-Do items, even when the app is closed.
            </p>
            {error && (
              <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
            )}
            {permission === "denied" ? (
              <p className="text-sm">
                Notifications are blocked. Update permissions in your browser
                settings.
              </p>
            ) : isSubscribed ? (
              <div className="flex flex-wrap items-center gap-3">
                <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700 dark:bg-green-950 dark:text-green-300">
                  On
                </span>
                <Button
                  variant="outline"
                  className="min-h-[44px] sm:min-h-0"
                  onClick={disable}
                >
                  Disable Notifications
                </Button>
              </div>
            ) : (
              <Button
                className="min-h-[44px] sm:min-h-0"
                onClick={enable}
              >
                Enable Notifications
              </Button>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

export default function SettingsPage({ user }: SettingsPageProps) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deletionRequested, setDeletionRequested] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const { logout } = useAuth();
  const queryClient = useQueryClient();

  const { data: subscription } = useQuery({
    queryKey: ["subscription"],
    queryFn: getSubscription,
    retry: false,
  });

  const { data: profile } = useQuery({
    queryKey: ["profile"],
    queryFn: getProfile,
    retry: false,
    enabled: user.role === "child",
  });

  async function handleCancel() {
    setCancelling(true);
    try {
      await cancelSubscription();
      queryClient.invalidateQueries({ queryKey: ["subscription"] });
    } catch {
      // ignore
    } finally {
      setCancelling(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Settings</h1>

      {user.role === "child" && profile && (
        <NicknameCard currentNickname={profile.nickname} />
      )}

      <Card>
        <CardHeader>
          <CardTitle>Subscription</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {subscription && (
            <>
              <div className="flex items-center gap-3">
                <span className="text-lg font-semibold">
                  {subscription.status === "active" ? "SizePass" : "Free"}
                </span>
                {subscription.status === "active" && (
                  <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
                    Active
                  </span>
                )}
              </div>
              {subscription.status === "active" && (user.role === "parent" || user.role === "admin") && (
                <Button
                  variant="destructive"
                  className="min-h-[44px] sm:min-h-0"
                  disabled={cancelling}
                  onClick={handleCancel}
                >
                  {cancelling ? "Cancelling..." : "Cancel Subscription"}
                </Button>
              )}
              {subscription.status !== "active" && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-950">
                  <p className="mb-2 text-sm text-muted-foreground">
                    Upgrade to SizePass for leaderboards, advanced stats, photo
                    proof, and more.
                  </p>
                  <Link to="/sizepass">
                    <Button variant="default">
                      Upgrade to SizePass
                    </Button>
                  </Link>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
      <PushNotificationsCard />
      <Card>
        <CardHeader>
          <CardTitle>Account</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {user.role === "child" && !deletionRequested && !showDeleteConfirm && (
            <Button
              variant="destructive"
              className="min-h-[44px] sm:min-h-0"
              onClick={() => setShowDeleteConfirm(true)}
            >
              Request Account Deletion
            </Button>
          )}
          {user.role === "child" && showDeleteConfirm && (
            <div className="rounded border border-red-200 bg-red-50 p-3 dark:border-red-800 dark:bg-red-950">
              <p className="text-sm">
                This action cannot be undone. Your parent will be asked to
                approve the deletion of your account and all your data.
              </p>
              <div className="mt-2 flex gap-2">
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={async () => {
                    await requestAccountDeletion();
                    setShowDeleteConfirm(false);
                    setDeletionRequested(true);
                  }}
                >
                  Confirm
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setShowDeleteConfirm(false)}
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}
          {user.role === "child" && deletionRequested && (
            <p className="text-sm text-muted-foreground">
              Your deletion request has been sent to your parent for approval.
            </p>
          )}
          {user.role === "parent" && !showDeleteConfirm && (
            <Button
              variant="destructive"
              className="min-h-[44px] sm:min-h-0"
              onClick={() => setShowDeleteConfirm(true)}
            >
              Delete My Account
            </Button>
          )}
          {user.role === "parent" && showDeleteConfirm && (
            <div className="rounded border border-red-200 bg-red-50 p-3 dark:border-red-800 dark:bg-red-950">
              <p className="text-sm">
                This action cannot be undone. Your account and all your data
                will be permanently deleted.
              </p>
              <div className="mt-2 flex gap-2">
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={async () => {
                    await deleteOwnAccount();
                    logout();
                  }}
                >
                  Confirm
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setShowDeleteConfirm(false)}
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

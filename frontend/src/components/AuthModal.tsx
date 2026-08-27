import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  login as apiLogin,
  adminLogin as apiAdminLogin,
  register as apiRegister,
  googleLoginStatus,
  API_URL,
} from "@/api";
import { useAuth } from "@/auth";
import { useLoading } from "@/hooks/useLoading";

function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [adminSecret, setAdminSecret] = useState("");
  const [googleErrorLocal, setGoogleErrorLocal] = useState<string | null>(null);
  const { isLoading, isSlow, error, execute } = useLoading();
  const { handleLogin } = useAuth();

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    execute(async () => {
      const { access_token } = isAdmin
        ? await apiAdminLogin(adminSecret)
        : await apiLogin(email, password);
      await handleLogin(access_token);
    }).catch(() => {});
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      {!isAdmin && (
        <>
          <div>
            <Label htmlFor="login-email">Email</Label>
            <Input
              id="login-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div>
            <Label htmlFor="login-password">Password</Label>
            <Input
              id="login-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
        </>
      )}
      {isAdmin && (
        <div>
          <Label htmlFor="admin-secret">Admin Secret</Label>
          <Input
            id="admin-secret"
            type="password"
            value={adminSecret}
            onChange={(e) => setAdminSecret(e.target.value)}
            required
          />
        </div>
      )}
      <div className="flex items-center gap-2">
        <Checkbox
          id="admin-toggle"
          checked={isAdmin}
          onCheckedChange={(v) => setIsAdmin(v === true)}
        />
        <Label htmlFor="admin-toggle">Login as Admin</Label>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button type="submit" className="w-full" disabled={isLoading}>
        {isLoading ? (
          <span className="flex items-center gap-2">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
            Logging in...
          </span>
        ) : (
          "Login"
        )}
      </Button>
      {googleErrorLocal && (
        <p className="text-sm text-destructive">{googleErrorLocal}</p>
      )}
      <Button
        type="button"
        variant="outline"
        className="w-full"
        disabled={isLoading}
        onClick={async () => {
          // Re-check on click: the mount-time check may have hit a cold-started
          // (sleeping) server and failed — Render free tier wakes in ~30 s.
          try {
            const status = await googleLoginStatus();
            if (status.enabled) {
              window.location.href = `${API_URL}/api/auth/google/authorize`;
              return;
            }
          } catch {
            // fall through to the message below
          }
          setGoogleErrorLocal(
            "Google login is not configured on the server. Use email and password.",
          );
        }}
      >
        <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
          <path
            fill="#EA4335"
            d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
          />
          <path
            fill="#4285F4"
            d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
          />
          <path
            fill="#FBBC05"
            d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
          />
          <path
            fill="#34A853"
            d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
          />
        </svg>
        Continue with Google
      </Button>
      {isSlow && (
        <p className="text-sm text-muted-foreground text-center">
          Serwer się budzi, może to chwilę potrwać...
        </p>
      )}
    </form>
  );
}

function RegisterForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"parent" | "child">("parent");
  const { isLoading, isSlow, error, execute } = useLoading();
  const { handleLogin } = useAuth();

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    execute(async () => {
      await apiRegister(email, password, role);
      const { access_token } = await apiLogin(email, password);
      await handleLogin(access_token);
    }).catch(() => {});
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div>
        <Label htmlFor="register-email">Email</Label>
        <Input
          id="register-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
      </div>
      <div>
        <Label htmlFor="register-password">Password</Label>
        <Input
          id="register-password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </div>
      <div>
        <Label htmlFor="register-role">Role</Label>
        <select
          id="register-role"
          value={role}
          onChange={(e) => setRole(e.target.value as "parent" | "child")}
          className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
        >
          <option value="parent">Parent</option>
          <option value="child">Child</option>
        </select>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button type="submit" className="w-full" disabled={isLoading}>
        {isLoading ? (
          <span className="flex items-center gap-2">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
            Registering...
          </span>
        ) : (
          "Register"
        )}
      </Button>
      {isSlow && (
        <p className="text-sm text-muted-foreground text-center">
          Serwer się budzi, może to chwilę potrwać...
        </p>
      )}
    </form>
  );
}

export default function AuthModal() {
  const [googleError] = useState(
    () => new URLSearchParams(window.location.search).get("google_error"),
  );

  return (
    <Dialog open modal>
      <DialogContent
        showCloseButton={false}
        onPointerDownOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => e.preventDefault()}
        onInteractOutside={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle>Welcome</DialogTitle>
          <DialogDescription>Sign in to continue</DialogDescription>
        </DialogHeader>
        {googleError && (
          <p className="text-sm text-destructive">
            Google sign-in failed ({googleError}). Try again or use email and
            password.
          </p>
        )}
        <Tabs defaultValue="login">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="login">Login</TabsTrigger>
            <TabsTrigger value="register">Register</TabsTrigger>
          </TabsList>
          <TabsContent value="login">
            <LoginForm />
          </TabsContent>
          <TabsContent value="register">
            <RegisterForm />
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}

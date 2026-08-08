let token: string | null = null;

export function setToken(t: string | null) {
  token = t;
}

export function getToken() {
  return token;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const base = import.meta.env.VITE_API_URL ?? "";
  const res = await fetch(`${base}${path}`, { ...options, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? "Request failed");
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export interface UserResponse {
  id: number;
  email: string;
  role: "parent" | "child" | "admin";
  language: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export function login(email: string, password: string) {
  return apiFetch<TokenResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function adminLogin(adminSecret: string) {
  return apiFetch<TokenResponse>("/api/auth/admin-login", {
    method: "POST",
    body: JSON.stringify({ admin_secret: adminSecret }),
  });
}

export function register(
  email: string,
  password: string,
  role: "parent" | "child",
) {
  return apiFetch<UserResponse>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, role }),
  });
}

export function getMe() {
  return apiFetch<UserResponse>("/api/auth/me");
}

// --- Family ---

export interface FamilyMember {
  id: number;
  email: string;
  role: string;
}

export interface FamilyResponse {
  id: number;
  pin: string;
  members: FamilyMember[];
}

export interface FamilyCreateResponse {
  id: number;
  pin: string;
}

export function getFamily() {
  return apiFetch<FamilyResponse>("/api/family");
}

export function createFamily() {
  return apiFetch<FamilyCreateResponse>("/api/family", { method: "POST" });
}

export function joinFamily(pin: string) {
  return apiFetch<{ family_id: number }>("/api/family/join", {
    method: "POST",
    body: JSON.stringify({ pin }),
  });
}

export function removeFamilyMember(userId: number) {
  return apiFetch<{ detail: string }>(`/api/family/members/${userId}`, {
    method: "DELETE",
  });
}

// --- Tasks ---

export interface TaskResponse {
  id: number;
  name: string;
  description: string;
  exbucks: number;
  status: "assigned" | "accepted" | "completed" | "approved" | "rejected";
  assigned_to: number;
  day_of_week: string | null;
  photo_url: string | null;
  avatar_icon: string | null;
  avatar_background: string | null;
}

export interface TaskCreateRequest {
  name: string;
  description: string;
  exbucks: number;
  assigned_to: number;
  day_of_week?: string | null;
}

export interface TaskEditRequest {
  name: string;
  description: string;
  exbucks: number;
  assigned_to: number;
  day_of_week?: string | null;
}

export function getTasks() {
  return apiFetch<TaskResponse[]>("/api/tasks");
}

export function createTask(data: TaskCreateRequest) {
  return apiFetch<TaskResponse>("/api/tasks", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function approveTask(taskId: number) {
  return apiFetch<TaskResponse>(`/api/tasks/${taskId}/approve`, {
    method: "PATCH",
  });
}

export function rejectTask(taskId: number) {
  return apiFetch<TaskResponse>(`/api/tasks/${taskId}/reject`, {
    method: "PATCH",
  });
}

export function acceptTask(taskId: number) {
  return apiFetch<TaskResponse>(`/api/tasks/${taskId}/accept`, {
    method: "PATCH",
  });
}

export function completeTask(taskId: number, photoUrl?: string) {
  return apiFetch<TaskResponse>(`/api/tasks/${taskId}/complete`, {
    method: "PATCH",
    body: JSON.stringify({ photo_url: photoUrl ?? null }),
  });
}

export function editTask(taskId: number, data: TaskEditRequest) {
  return apiFetch<TaskResponse>(`/api/tasks/${taskId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export function deleteTask(taskId: number) {
  return apiFetch<void>(`/api/tasks/${taskId}`, {
    method: "DELETE",
  });
}

// --- ExBucks ---

export interface BalanceResponse {
  balance: number;
}

export interface TransactionResponse {
  id: number;
  type: string;
  amount: number;
  description: string;
  created_at: string;
}

export interface PenaltyRequest {
  child_id: number;
  amount: number;
  reason: string;
}

export function getBalance() {
  return apiFetch<BalanceResponse>("/api/exbucks/balance");
}

export function getTransactions() {
  return apiFetch<TransactionResponse[]>("/api/exbucks/transactions");
}

export function getChildTransactions(childId: number) {
  return apiFetch<TransactionResponse[]>(
    `/api/exbucks/transactions/${childId}`,
  );
}

export function assignPenalty(data: PenaltyRequest) {
  return apiFetch<TransactionResponse>("/api/exbucks/penalty", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// --- Gamification ---

export interface GamificationProfileResponse {
  xp: number;
  level: number;
  level_name: string;
  progress_percent: number;
  xp_for_next_level: number;
  streak: number;
}

export function getGamificationProfile() {
  return apiFetch<GamificationProfileResponse>("/api/gamification/profile");
}

// --- Profile ---

export interface ProfileTransactionItem {
  id: number;
  type: string;
  amount: number;
  description: string;
  created_at: string;
}

export interface ProfileResponse {
  nickname: string | null;
  nickname_changes: number;
  xp: number;
  level: number;
  level_name: string;
  progress_percent: number;
  xp_for_next_level: number;
  streak: number;
  exbucks_balance: number;
  badges: string[];
  transactions: ProfileTransactionItem[];
}

export function getProfile() {
  return apiFetch<ProfileResponse>("/api/profile");
}

export function getChildProfile(childId: number) {
  return apiFetch<ProfileResponse>(`/api/profile/${childId}`);
}

export interface NicknameResponse {
  nickname: string;
  nickname_changes: number;
}

export function setNickname(nickname: string) {
  return apiFetch<NicknameResponse>("/api/profile/nickname", {
    method: "PATCH",
    body: JSON.stringify({ nickname }),
  });
}

// --- Dashboard ---

export interface DashboardChildStats {
  id: number;
  email: string;
  tasks_completed_percent: number;
  streak: number;
  exbucks_earned: number;
  exbucks_spent: number;
}

export interface DashboardDayChild {
  child_id: number;
  email: string;
  total: number;
  approved: number;
}

export interface DashboardAdvancedChildStats {
  id: number;
  email: string;
  total_tasks: number;
  approved_tasks: number;
  xp: number;
  level: number;
}

export interface DashboardAdvancedStats {
  total_xp_earned: number;
  best_streak: number;
  children: DashboardAdvancedChildStats[];
}

export interface DashboardResponse {
  children: DashboardChildStats[];
  weekly_overview: Record<string, DashboardDayChild[]>;
  advanced_stats: DashboardAdvancedStats | null;
}

export function getDashboard() {
  return apiFetch<DashboardResponse>("/api/dashboard");
}

// --- Subscription ---

export interface SubscriptionResponse {
  plan: string;
  status: string;
}

export function getSubscription() {
  return apiFetch<SubscriptionResponse>("/api/subscription");
}

export function checkout(plan: "monthly" | "yearly") {
  return apiFetch<SubscriptionResponse>("/api/subscription/checkout", {
    method: "POST",
    body: JSON.stringify({ plan }),
  });
}

export function cancelSubscription() {
  return apiFetch<SubscriptionResponse>("/api/subscription/cancel", {
    method: "POST",
  });
}

// --- Leaderboard ---

export interface LeaderboardEntry {
  id: number;
  email: string;
  nickname: string | null;
  avatar_icon: string | null;
  avatar_background: string | null;
  xp: number;
  level: number;
  streak: number;
}

export interface LeaderboardResponse {
  entries: LeaderboardEntry[];
}

export function getLeaderboard() {
  return apiFetch<LeaderboardResponse>("/api/leaderboard");
}

export interface GlobalLeaderboardEntry {
  id: number;
  email: string;
  nickname: string | null;
  avatar_icon: string | null;
  avatar_background: string | null;
  xp: number;
  level: number;
  streak: number;
  position: number;
}

export interface GlobalLeaderboardResponse {
  entries: GlobalLeaderboardEntry[];
  user_entry: GlobalLeaderboardEntry | null;
}

export function getGlobalLeaderboard() {
  return apiFetch<GlobalLeaderboardResponse>("/api/leaderboard/global");
}

// --- Admin Settings ---

export interface AppSettingsResponse {
  max_exbucks_per_task: number;
}

export interface UpdateAppSettingsRequest {
  max_exbucks_per_task: number;
}

export function getAppSettings() {
  return apiFetch<AppSettingsResponse>("/api/admin/settings");
}

export function getPublicSettings() {
  return apiFetch<AppSettingsResponse>("/api/admin/settings/public");
}

export function updateAppSettings(data: UpdateAppSettingsRequest) {
  return apiFetch<AppSettingsResponse>("/api/admin/settings", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

// --- Avatar ---

export interface AvatarItemResponse {
  id: number;
  type: "icon" | "background";
  value: string;
  label: string;
  price: number;
  is_default: boolean;
  active_in_shop: boolean;
}

export interface AvatarItemCreateRequest {
  type: "icon" | "background";
  value: string;
  label: string;
  price: number;
}

export interface AvatarItemUpdateRequest {
  label?: string;
  price?: number;
  active_in_shop?: boolean;
}

export interface EquippedAvatarResponse {
  icon: AvatarItemResponse | null;
  background: AvatarItemResponse | null;
}

export function getAvatarItems() {
  return apiFetch<AvatarItemResponse[]>("/api/avatar/items");
}

export function getAvatarShop() {
  return apiFetch<AvatarItemResponse[]>("/api/avatar/shop");
}

export function getAvatarInventory() {
  return apiFetch<AvatarItemResponse[]>("/api/avatar/inventory");
}

export function purchaseAvatarItem(itemId: number) {
  return apiFetch<{ detail: string }>(`/api/avatar/purchase/${itemId}`, {
    method: "POST",
  });
}

export function equipAvatarItem(itemId: number) {
  return apiFetch<{ detail: string }>(`/api/avatar/equip/${itemId}`, {
    method: "POST",
  });
}

export function unequipAvatarItem(type: "icon" | "background") {
  return apiFetch<{ detail: string }>(`/api/avatar/unequip/${type}`, {
    method: "POST",
  });
}

export function createAvatarItem(data: AvatarItemCreateRequest) {
  return apiFetch<AvatarItemResponse>("/api/avatar/items", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateAvatarItem(itemId: number, data: AvatarItemUpdateRequest) {
  return apiFetch<AvatarItemResponse>(`/api/avatar/items/${itemId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteAvatarItem(itemId: number) {
  return apiFetch<{ detail: string }>(`/api/avatar/items/${itemId}`, {
    method: "DELETE",
  });
}

export function getEquippedAvatar(userId: number) {
  return apiFetch<EquippedAvatarResponse>(`/api/avatar/equipped/${userId}`);
}

// --- Account ---

export interface DeletionRequestResponse {
  id: number;
  child_id: number;
  status: string;
}

export function deleteChildAccount(childId: number) {
  return apiFetch<{ detail: string }>(
    `/api/account/children/${childId}?confirm=true`,
    { method: "DELETE" },
  );
}

export function deleteOwnAccount() {
  return apiFetch<{ detail: string }>("/api/account/me?confirm=true", {
    method: "DELETE",
  });
}

export function requestAccountDeletion() {
  return apiFetch<DeletionRequestResponse>("/api/account/deletion-requests", {
    method: "POST",
  });
}

export function getDeletionRequests() {
  return apiFetch<DeletionRequestResponse[]>("/api/account/deletion-requests");
}

export function approveDeletionRequest(requestId: number) {
  return apiFetch<{ detail: string }>(
    `/api/account/deletion-requests/${requestId}/approve`,
    { method: "POST" },
  );
}

// --- Todo (ExSize 2.0) ---

export type TodoRecurrence = "daily" | "weekly";

export interface TodoItemResponse {
  id: number;
  title: string;
  completed: boolean;
  dueAt: string | null;
  recurrence: TodoRecurrence | null;
}

export interface TodoListResponse {
  id: number;
  name: string;
  items: TodoItemResponse[];
}

export function getTodoLists() {
  return apiFetch<TodoListResponse[]>("/api/todo/lists");
}

export function createTodoList(name: string) {
  return apiFetch<TodoListResponse>("/api/todo/lists", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export function renameTodoList(listId: number, name: string) {
  return apiFetch<TodoListResponse>(`/api/todo/lists/${listId}`, {
    method: "PUT",
    body: JSON.stringify({ name }),
  });
}

export function deleteTodoList(listId: number) {
  return apiFetch<void>(`/api/todo/lists/${listId}`, { method: "DELETE" });
}

export function addTodoItem(
  listId: number,
  title: string,
  dueAt?: string | null,
  recurrence?: TodoRecurrence | null,
) {
  return apiFetch<TodoItemResponse>(`/api/todo/lists/${listId}/items`, {
    method: "POST",
    body: JSON.stringify({ title, due_at: dueAt ?? null, recurrence: recurrence ?? null }),
  });
}

export function completeTodoItem(itemId: number) {
  return apiFetch<TodoItemResponse>(`/api/todo/items/${itemId}/complete`, {
    method: "PATCH",
  });
}

export function editTodoItem(itemId: number, title: string) {
  return apiFetch<TodoItemResponse>(`/api/todo/items/${itemId}`, {
    method: "PUT",
    body: JSON.stringify({ title }),
  });
}

export function setTodoItemDue(itemId: number, dueAt: string | null) {
  return apiFetch<TodoItemResponse>(`/api/todo/items/${itemId}/due`, {
    method: "PATCH",
    body: JSON.stringify({ due_at: dueAt }),
  });
}

export function setTodoItemRecurrence(
  itemId: number,
  recurrence: TodoRecurrence | null,
) {
  return apiFetch<TodoItemResponse>(`/api/todo/items/${itemId}/recurrence`, {
    method: "PATCH",
    body: JSON.stringify({ recurrence }),
  });
}

export function deleteTodoItem(itemId: number) {
  return apiFetch<void>(`/api/todo/items/${itemId}`, { method: "DELETE" });
}

// --- Push notifications (ExSize 2.0, issue #64) ---

export interface PushPublicKeyResponse {
  public_key: string;
}

export interface PushSubscriptionKeys {
  p256dh: string;
  auth: string;
}

export interface PushSubscribeRequest {
  endpoint: string;
  keys: PushSubscriptionKeys;
}

export function getVapidPublicKey() {
  return apiFetch<PushPublicKeyResponse>("/api/push/vapid-public-key");
}

export function subscribePush(data: PushSubscribeRequest) {
  return apiFetch<{ detail: string }>("/api/push/subscribe", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function unsubscribePush(endpoint: string) {
  return apiFetch<{ detail: string }>("/api/push/unsubscribe", {
    method: "POST",
    body: JSON.stringify({ endpoint }),
  });
}

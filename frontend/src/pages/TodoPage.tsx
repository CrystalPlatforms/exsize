import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  getTodoLists,
  createTodoList,
  renameTodoList,
  deleteTodoList,
  addTodoItem,
  completeTodoItem,
  editTodoItem,
  deleteTodoItem,
  setTodoItemDue,
  setTodoItemRecurrence,
  type TodoListResponse,
  type TodoRecurrence,
} from "@/api";

const RECURRENCE_OPTIONS: TodoRecurrence[] = ["daily", "weekly"];

function recurrenceBadge(recurrence: TodoRecurrence | null): { text: string; className: string } | null {
  if (!recurrence) return null;
  return {
    text: `Repeats ${recurrence}`,
    className: "rounded bg-purple-100 px-1.5 py-0.5 text-xs font-medium text-purple-700",
  };
}

function formatDue(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function dueBadge(item: { dueAt: string | null; completed: boolean }): { text: string; className: string } | null {
  if (!item.dueAt || item.completed) return null;
  const overdue = new Date(item.dueAt).getTime() <= Date.now();
  return overdue
    ? { text: "Overdue", className: "rounded bg-red-100 px-1.5 py-0.5 text-xs font-medium text-red-700" }
    : { text: "Upcoming", className: "rounded bg-blue-100 px-1.5 py-0.5 text-xs font-medium text-blue-700" };
}

function toDatetimeLocalValue(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function TodoPage() {
  const queryClient = useQueryClient();
  const [newListName, setNewListName] = useState("");
  const [newItemTitles, setNewItemTitles] = useState<Record<number, string>>(
    {},
  );
  const [newItemDue, setNewItemDue] = useState<Record<number, string>>({});
  const [newItemRecurrence, setNewItemRecurrence] = useState<
    Record<number, TodoRecurrence | undefined>
  >({});
  const [editingItemId, setEditingItemId] = useState<number | null>(null);
  const [editItemTitle, setEditItemTitle] = useState("");
  const [dueItemId, setDueItemId] = useState<number | null>(null);
  const [dueValue, setDueValue] = useState("");
  const [recurrenceItemId, setRecurrenceItemId] = useState<number | null>(null);
  const [recurrenceValue, setRecurrenceValue] = useState<TodoRecurrence | "">("");
  const [renamingListId, setRenamingListId] = useState<number | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deletingListId, setDeletingListId] = useState<number | null>(null);

  const { data: lists, isLoading } = useQuery({
    queryKey: ["todo-lists"],
    queryFn: getTodoLists,
    retry: false,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["todo-lists"] });

  const createListM = useMutation({
    mutationFn: createTodoList,
    onSuccess: () => {
      invalidate();
      setNewListName("");
    },
  });

  const renameListM = useMutation({
    mutationFn: (v: { id: number; name: string }) => renameTodoList(v.id, v.name),
    onSuccess: () => {
      invalidate();
      setRenamingListId(null);
    },
  });

  const deleteListM = useMutation({
    mutationFn: deleteTodoList,
    onSuccess: () => {
      invalidate();
      setDeletingListId(null);
    },
  });

  const addItemM = useMutation({
    mutationFn: (v: {
      listId: number;
      title: string;
      dueAt?: string;
      recurrence?: TodoRecurrence;
    }) => addTodoItem(v.listId, v.title, v.dueAt, v.recurrence),
    onSuccess: (_data, vars) => {
      invalidate();
      setNewItemTitles((prev) => ({ ...prev, [vars.listId]: "" }));
      setNewItemDue((prev) => ({ ...prev, [vars.listId]: "" }));
      setNewItemRecurrence((prev) => ({ ...prev, [vars.listId]: undefined }));
    },
  });

  const completeM = useMutation({
    mutationFn: completeTodoItem,
    onSuccess: invalidate,
  });

  const editItemM = useMutation({
    mutationFn: (v: { id: number; title: string }) => editTodoItem(v.id, v.title),
    onSuccess: () => {
      invalidate();
      setEditingItemId(null);
    },
  });

  const deleteItemM = useMutation({
    mutationFn: deleteTodoItem,
    onSuccess: invalidate,
  });

  const setDueM = useMutation({
    mutationFn: (v: { id: number; dueAt: string | null }) => setTodoItemDue(v.id, v.dueAt),
    onSuccess: () => {
      invalidate();
      setDueItemId(null);
    },
  });

  const setRecurrenceM = useMutation({
    mutationFn: (v: { id: number; recurrence: TodoRecurrence | null }) =>
      setTodoItemRecurrence(v.id, v.recurrence),
    onSuccess: () => {
      invalidate();
      setRecurrenceItemId(null);
    },
  });

  if (isLoading) return <div>Loading...</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">To-Do</h1>

      <Card>
        <CardHeader>
          <CardTitle>New list</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              const name = newListName.trim();
              if (!name) return;
              createListM.mutate(name);
            }}
          >
            <div className="flex-1">
              <Label htmlFor="new-list-name" className="sr-only">
                List name
              </Label>
              <Input
                id="new-list-name"
                value={newListName}
                onChange={(e) => setNewListName(e.target.value)}
                placeholder="List name"
              />
            </div>
            <Button type="submit" disabled={createListM.isPending}>
              Create list
            </Button>
          </form>
        </CardContent>
      </Card>

      {(lists ?? []).map((list: TodoListResponse) => (
        <Card key={list.id}>
          <CardHeader>
            {renamingListId === list.id ? (
              <form
                className="flex flex-wrap gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  const name = renameValue.trim();
                  if (!name) return;
                  renameListM.mutate({ id: list.id, name });
                }}
              >
                <Label htmlFor={`rename-${list.id}`} className="sr-only">
                  Edit list name
                </Label>
                <Input
                  id={`rename-${list.id}`}
                  value={renameValue}
                  onChange={(e) => setRenameValue(e.target.value)}
                />
                <Button type="submit" size="sm" disabled={renameListM.isPending}>
                  Save list name
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => setRenamingListId(null)}
                >
                  Cancel
                </Button>
              </form>
            ) : (
              <div className="flex flex-wrap items-center justify-between gap-2">
                <CardTitle>{list.name}</CardTitle>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    aria-label={`Rename list "${list.name}"`}
                    onClick={() => {
                      setRenamingListId(list.id);
                      setRenameValue(list.name);
                    }}
                  >
                    Rename list
                  </Button>
                  <Button
                    size="sm"
                    variant="destructive"
                    aria-label={`Delete list "${list.name}"`}
                    onClick={() => setDeletingListId(list.id)}
                  >
                    Delete list
                  </Button>
                </div>
              </div>
            )}
          </CardHeader>
          <CardContent className="space-y-3">
            <form
              className="flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                const title = (newItemTitles[list.id] ?? "").trim();
                if (!title) return;
                addItemM.mutate({
                  listId: list.id,
                  title,
                  dueAt: newItemDue[list.id] || undefined,
                  recurrence: newItemRecurrence[list.id],
                });
              }}
            >
              <div className="flex-1">
                <Label htmlFor={`new-item-${list.id}`} className="sr-only">
                  Add item to "{list.name}"
                </Label>
                <Input
                  id={`new-item-${list.id}`}
                  value={newItemTitles[list.id] ?? ""}
                  onChange={(e) =>
                    setNewItemTitles((prev) => ({
                      ...prev,
                      [list.id]: e.target.value,
                    }))
                  }
                  placeholder="Add an item"
                />
              </div>
              <div>
                <Label htmlFor={`new-item-due-${list.id}`} className="sr-only">
                  Due date
                </Label>
                <Input
                  id={`new-item-due-${list.id}`}
                  type="datetime-local"
                  value={newItemDue[list.id] ?? ""}
                  onChange={(e) =>
                    setNewItemDue((prev) => ({
                      ...prev,
                      [list.id]: e.target.value,
                    }))
                  }
                />
              </div>
              <div>
                <Label htmlFor={`new-item-recurrence-${list.id}`} className="sr-only">
                  Repeats
                </Label>
                <select
                  id={`new-item-recurrence-${list.id}`}
                  className="h-9 rounded-md border border-input bg-background px-2 text-sm"
                  value={newItemRecurrence[list.id] ?? ""}
                  onChange={(e) =>
                    setNewItemRecurrence((prev) => ({
                      ...prev,
                      [list.id]:
                        (e.target.value as TodoRecurrence | "") || undefined,
                    }))
                  }
                >
                  <option value="">One-off</option>
                  {RECURRENCE_OPTIONS.map((r) => (
                    <option key={r} value={r}>
                      {r === "daily" ? "Daily" : "Weekly"}
                    </option>
                  ))}
                </select>
              </div>
              <Button type="submit" size="sm" disabled={addItemM.isPending}>
                Add
              </Button>
            </form>

            <div className="space-y-1">
              {list.items.map((item) => (
                <div
                  key={item.id}
                  className="flex flex-wrap items-center gap-2 rounded border p-2"
                >
                  {editingItemId === item.id ? (
                    <form
                      className="flex flex-1 flex-wrap gap-2"
                      onSubmit={(e) => {
                        e.preventDefault();
                        const title = editItemTitle.trim();
                        if (!title) return;
                        editItemM.mutate({ id: item.id, title });
                      }}
                    >
                      <Label htmlFor={`edit-item-${item.id}`} className="sr-only">
                        Edit item title
                      </Label>
                      <Input
                        id={`edit-item-${item.id}`}
                        value={editItemTitle}
                        onChange={(e) => setEditItemTitle(e.target.value)}
                      />
                      <Button
                        type="submit"
                        size="sm"
                        disabled={editItemM.isPending}
                      >
                        Save item
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => setEditingItemId(null)}
                      >
                        Cancel
                      </Button>
                    </form>
                  ) : (
                    <>
                      <Checkbox
                        checked={item.completed}
                        aria-label={`Toggle "${item.title}"`}
                        onCheckedChange={() => completeM.mutate(item.id)}
                      />
                      <span
                        className={`flex-1 ${item.completed ? "line-through text-muted-foreground" : ""}`}
                      >
                        {item.title}
                      </span>
                      {item.dueAt && (
                        <span className="text-xs text-muted-foreground">
                          {formatDue(item.dueAt)}
                        </span>
                      )}
                      {(() => {
                        const badge = dueBadge(item);
                        return badge ? <span className={badge.className}>{badge.text}</span> : null;
                      })()}
                      {(() => {
                        const badge = recurrenceBadge(item.recurrence);
                        return badge ? <span className={badge.className}>{badge.text}</span> : null;
                      })()}
                      <Button
                        size="sm"
                        variant="outline"
                        aria-label={`Edit item "${item.title}"`}
                        onClick={() => {
                          setEditingItemId(item.id);
                          setEditItemTitle(item.title);
                        }}
                      >
                        Edit item
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        aria-label={`Set due for "${item.title}"`}
                        onClick={() => {
                          setDueItemId(item.id);
                          setDueValue(item.dueAt ? toDatetimeLocalValue(item.dueAt) : "");
                        }}
                      >
                        Set due
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        aria-label={`Set recurrence for "${item.title}"`}
                        onClick={() => {
                          setRecurrenceItemId(item.id);
                          setRecurrenceValue(item.recurrence ?? "");
                        }}
                      >
                        Set recurrence
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        aria-label={`Delete item "${item.title}"`}
                        onClick={() => deleteItemM.mutate(item.id)}
                      >
                        Delete item
                      </Button>
                    </>
                  )}
                  {dueItemId === item.id && (
                    <div className="mt-2 flex w-full flex-wrap items-center gap-2">
                      <Label htmlFor={`set-due-${item.id}`} className="sr-only">
                        Set due date
                      </Label>
                      <Input
                        id={`set-due-${item.id}`}
                        type="datetime-local"
                        value={dueValue}
                        onChange={(e) => setDueValue(e.target.value)}
                      />
                      <Button
                        size="sm"
                        disabled={setDueM.isPending}
                        onClick={() =>
                          setDueM.mutate({ id: item.id, dueAt: dueValue || null })
                        }
                      >
                        Save due
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setDueM.mutate({ id: item.id, dueAt: null })}
                      >
                        Clear due
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setDueItemId(null)}
                      >
                        Cancel
                      </Button>
                    </div>
                  )}
                  {recurrenceItemId === item.id && (
                    <div className="mt-2 flex w-full flex-wrap items-center gap-2">
                      <Label htmlFor={`set-recurrence-${item.id}`} className="sr-only">
                        Set recurrence
                      </Label>
                      <select
                        id={`set-recurrence-${item.id}`}
                        className="h-9 rounded-md border border-input bg-background px-2 text-sm"
                        value={recurrenceValue}
                        onChange={(e) =>
                          setRecurrenceValue((e.target.value as TodoRecurrence | "") || "")
                        }
                      >
                        <option value="">One-off</option>
                        {RECURRENCE_OPTIONS.map((r) => (
                          <option key={r} value={r}>
                            {r === "daily" ? "Daily" : "Weekly"}
                          </option>
                        ))}
                      </select>
                      <Button
                        size="sm"
                        disabled={setRecurrenceM.isPending}
                        onClick={() =>
                          setRecurrenceM.mutate({
                            id: item.id,
                            recurrence: recurrenceValue || null,
                          })
                        }
                      >
                        Save recurrence
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          setRecurrenceM.mutate({ id: item.id, recurrence: null })
                        }
                      >
                        Clear recurrence
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setRecurrenceItemId(null)}
                      >
                        Cancel
                      </Button>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {deletingListId === list.id && (
              <div className="rounded border border-red-200 bg-red-50 p-3">
                <p className="text-sm">
                  Are you sure you want to delete this list and all its items?
                </p>
                <div className="mt-2 flex gap-2">
                  <Button
                    size="sm"
                    variant="destructive"
                    disabled={deleteListM.isPending}
                    onClick={() => deleteListM.mutate(list.id)}
                  >
                    Confirm
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setDeletingListId(null)}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

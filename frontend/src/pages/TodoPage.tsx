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
  type TodoListResponse,
} from "@/api";

export default function TodoPage() {
  const queryClient = useQueryClient();
  const [newListName, setNewListName] = useState("");
  const [newItemTitles, setNewItemTitles] = useState<Record<number, string>>(
    {},
  );
  const [editingItemId, setEditingItemId] = useState<number | null>(null);
  const [editItemTitle, setEditItemTitle] = useState("");
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
    mutationFn: (v: { listId: number; title: string }) =>
      addTodoItem(v.listId, v.title),
    onSuccess: (_data, vars) => {
      invalidate();
      setNewItemTitles((prev) => ({ ...prev, [vars.listId]: "" }));
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
                addItemM.mutate({ listId: list.id, title });
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
                        variant="destructive"
                        aria-label={`Delete item "${item.title}"`}
                        onClick={() => deleteItemM.mutate(item.id)}
                      >
                        Delete item
                      </Button>
                    </>
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

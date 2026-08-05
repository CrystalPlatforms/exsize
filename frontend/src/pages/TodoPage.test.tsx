import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider } from "@/auth";
import TodoPage from "@/pages/TodoPage";

vi.mock("@/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api")>();
  return {
    ...actual,
    getTodoLists: vi.fn(),
    createTodoList: vi.fn(),
    renameTodoList: vi.fn(),
    deleteTodoList: vi.fn(),
    addTodoItem: vi.fn(),
    completeTodoItem: vi.fn(),
    editTodoItem: vi.fn(),
    deleteTodoItem: vi.fn(),
    setTodoItemDue: vi.fn(),
    setTodoItemRecurrence: vi.fn(),
    getMe: vi.fn(),
    setToken: vi.fn(),
  };
});

import {
  getTodoLists as getTodoListsMock,
  createTodoList as createTodoListMock,
  renameTodoList as renameTodoListMock,
  deleteTodoList as deleteTodoListMock,
  addTodoItem as addTodoItemMock,
  completeTodoItem as completeTodoItemMock,
  editTodoItem as editTodoItemMock,
  deleteTodoItem as deleteTodoItemMock,
  setTodoItemDue as setTodoItemDueMock,
  setTodoItemRecurrence as setTodoItemRecurrenceMock,
} from "@/api";

function renderTodoPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter>
          <TodoPage />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

const ITEM = { id: 1, title: "Mleko", completed: false, dueAt: null, recurrence: null };
const EMPTY_LIST = { id: 1, name: "Zakupy", items: [] };
const LIST_WITH_ITEM = { id: 1, name: "Zakupy", items: [ITEM] };

describe("TodoPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders existing todo lists and items", async () => {
    vi.mocked(getTodoListsMock).mockResolvedValue([LIST_WITH_ITEM]);
    renderTodoPage();
    expect(await screen.findByText("Zakupy")).toBeInTheDocument();
    expect(screen.getByText("Mleko")).toBeInTheDocument();
  });

  it("creates a list when the form is submitted", async () => {
    const user = userEvent.setup();
    vi.mocked(getTodoListsMock).mockResolvedValue([]);
    vi.mocked(createTodoListMock).mockResolvedValue({
      id: 1,
      name: "Praca",
      items: [],
    });

    renderTodoPage();
    await screen.findByText("To-Do");

    await user.type(screen.getByLabelText(/list name/i), "Praca");
    await user.click(screen.getByRole("button", { name: /create list/i }));

    await waitFor(() =>
      expect(createTodoListMock).toHaveBeenCalledWith("Praca", expect.anything()),
    );
  });

  it("adds an item to a list", async () => {
    const user = userEvent.setup();
    vi.mocked(getTodoListsMock).mockResolvedValue([EMPTY_LIST]);
    vi.mocked(addTodoItemMock).mockResolvedValue({
      id: 1,
      title: "Chleb",
      completed: false,
      dueAt: null,
      recurrence: null,
    });

    renderTodoPage();
    await screen.findByText("Zakupy");

    await user.type(screen.getByLabelText(/add item to/i), "Chleb");
    await user.click(screen.getByRole("button", { name: /^add$/i }));

    await waitFor(() =>
      expect(addTodoItemMock).toHaveBeenCalledWith(1, "Chleb", undefined, undefined),
    );
  });

  it("toggles an item complete via the checkbox", async () => {
    const user = userEvent.setup();
    vi.mocked(getTodoListsMock).mockResolvedValue([LIST_WITH_ITEM]);
    vi.mocked(completeTodoItemMock).mockResolvedValue({
      id: 1,
      title: "Mleko",
      completed: true,
      dueAt: null,
      recurrence: null,
    });

    renderTodoPage();
    await screen.findByText("Mleko");

    await user.click(
      screen.getByRole("checkbox", { name: /toggle.*mleko/i }),
    );

    await waitFor(() => expect(completeTodoItemMock).toHaveBeenCalledWith(1, expect.anything()));
  });

  it("edits an item inline", async () => {
    const user = userEvent.setup();
    vi.mocked(getTodoListsMock).mockResolvedValue([LIST_WITH_ITEM]);
    vi.mocked(editTodoItemMock).mockResolvedValue({
      id: 1,
      title: "Mleko 2%",
      completed: false,
      dueAt: null,
      recurrence: null,
    });

    renderTodoPage();
    await screen.findByText("Mleko");

    await user.click(screen.getByRole("button", { name: /edit item/i }));
    const input = screen.getByLabelText(/edit item title/i);
    expect(input).toHaveValue("Mleko");
    await user.clear(input);
    await user.type(input, "Mleko 2%");
    await user.click(screen.getByRole("button", { name: /save item/i }));

    await waitFor(() =>
      expect(editTodoItemMock).toHaveBeenCalledWith(1, "Mleko 2%"),
    );
  });

  it("deletes an item", async () => {
    const user = userEvent.setup();
    vi.mocked(getTodoListsMock).mockResolvedValue([LIST_WITH_ITEM]);
    vi.mocked(deleteTodoItemMock).mockResolvedValue(undefined);

    renderTodoPage();
    await screen.findByText("Mleko");

    await user.click(screen.getByRole("button", { name: /delete item/i }));

    await waitFor(() => expect(deleteTodoItemMock).toHaveBeenCalledWith(1, expect.anything()));
  });

  it("renames a list inline", async () => {
    const user = userEvent.setup();
    vi.mocked(getTodoListsMock).mockResolvedValue([EMPTY_LIST]);
    vi.mocked(renameTodoListMock).mockResolvedValue({
      id: 1,
      name: "Codzienne",
      items: [],
    });

    renderTodoPage();
    await screen.findByText("Zakupy");

    await user.click(screen.getByRole("button", { name: /rename list/i }));
    const input = screen.getByLabelText(/edit list name/i);
    expect(input).toHaveValue("Zakupy");
    await user.clear(input);
    await user.type(input, "Codzienne");
    await user.click(screen.getByRole("button", { name: /save list name/i }));

    await waitFor(() =>
      expect(renameTodoListMock).toHaveBeenCalledWith(1, "Codzienne"),
    );
  });

  it("deletes a list after confirmation", async () => {
    const user = userEvent.setup();
    vi.mocked(getTodoListsMock).mockResolvedValue([EMPTY_LIST]);
    vi.mocked(deleteTodoListMock).mockResolvedValue(undefined);

    renderTodoPage();
    await screen.findByText("Zakupy");

    await user.click(screen.getByRole("button", { name: /delete list/i }));
    expect(screen.getByText(/are you sure/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /confirm/i }));

    await waitFor(() => expect(deleteTodoListMock).toHaveBeenCalledWith(1, expect.anything()));
  });

  it("shows the formatted due date for an item with one", async () => {
    vi.mocked(getTodoListsMock).mockResolvedValue([
      {
        id: 1,
        name: "Zakupy",
        items: [
          { id: 2, title: "Mleko", completed: false, dueAt: "2026-08-06T18:00:00", recurrence: null },
        ],
      },
    ]);

    renderTodoPage();
    await screen.findByText("Mleko");

    expect(screen.getByText("06.08.2026 18:00")).toBeInTheDocument();
  });

  it("flags an overdue uncompleted item with an Overdue badge", async () => {
    vi.mocked(getTodoListsMock).mockResolvedValue([
      {
        id: 1,
        name: "Zakupy",
        items: [{ id: 2, title: "Mleko", completed: false, dueAt: "2020-01-01T08:00:00", recurrence: null }],
      },
    ]);

    renderTodoPage();
    await screen.findByText("Mleko");

    expect(screen.getByText(/overdue/i)).toBeInTheDocument();
  });

  it("flags an upcoming item with an Upcoming badge", async () => {
    vi.mocked(getTodoListsMock).mockResolvedValue([
      {
        id: 1,
        name: "Zakupy",
        items: [{ id: 2, title: "Mleko", completed: false, dueAt: "2099-01-01T08:00:00", recurrence: null }],
      },
    ]);

    renderTodoPage();
    await screen.findByText("Mleko");

    expect(screen.getByText(/upcoming/i)).toBeInTheDocument();
  });

  it("does not flag a completed overdue item", async () => {
    vi.mocked(getTodoListsMock).mockResolvedValue([
      {
        id: 1,
        name: "Zakupy",
        items: [{ id: 2, title: "Mleko", completed: true, dueAt: "2020-01-01T08:00:00", recurrence: null }],
      },
    ]);

    renderTodoPage();
    await screen.findByText("Mleko");

    expect(screen.queryByText(/overdue|upcoming/i)).not.toBeInTheDocument();
  });

  it("adds an item with a due date", async () => {
    const user = userEvent.setup();
    vi.mocked(getTodoListsMock).mockResolvedValue([EMPTY_LIST]);
    vi.mocked(addTodoItemMock).mockResolvedValue({
      id: 1,
      title: "Chleb",
      completed: false,
      dueAt: null,
      recurrence: null,
    });

    renderTodoPage();
    await screen.findByText("Zakupy");

    await user.type(screen.getByLabelText(/add item to/i), "Chleb");
    await user.type(screen.getByLabelText(/due date/i), "2026-08-06T12:00");
    await user.click(screen.getByRole("button", { name: /^add$/i }));

    await waitFor(() =>
      expect(addTodoItemMock).toHaveBeenCalledWith(1, "Chleb", "2026-08-06T12:00", undefined),
    );
  });

  it("sets a due date on an existing item", async () => {
    const user = userEvent.setup();
    vi.mocked(getTodoListsMock).mockResolvedValue([LIST_WITH_ITEM]);
    vi.mocked(setTodoItemDueMock).mockResolvedValue({
      id: 1,
      title: "Mleko",
      completed: false,
      dueAt: "2026-08-06T12:00:00",
      recurrence: null,
    });

    renderTodoPage();
    await screen.findByText("Mleko");

    await user.click(screen.getByRole("button", { name: /set due/i }));
    const input = screen.getByLabelText(/set due date/i);
    await user.type(input, "2026-08-06T12:00");
    await user.click(screen.getByRole("button", { name: /save due/i }));

    await waitFor(() =>
      expect(setTodoItemDueMock).toHaveBeenCalledWith(1, "2026-08-06T12:00"),
    );
  });

  it("clears the due date on an existing item", async () => {
    const user = userEvent.setup();
    vi.mocked(getTodoListsMock).mockResolvedValue([
      {
        id: 1,
        name: "Zakupy",
        items: [
          { id: 1, title: "Mleko", completed: false, dueAt: "2026-08-06T12:00:00", recurrence: null },
        ],
      },
    ]);
    vi.mocked(setTodoItemDueMock).mockResolvedValue({
      id: 1,
      title: "Mleko",
      completed: false,
      dueAt: null,
      recurrence: null,
    });

    renderTodoPage();
    await screen.findByText("Mleko");

    await user.click(screen.getByRole("button", { name: /set due/i }));
    await user.click(screen.getByRole("button", { name: /clear due/i }));

    await waitFor(() => expect(setTodoItemDueMock).toHaveBeenCalledWith(1, null));
  });

  // --- Recurrence (issue #62) ---

  it("adds a recurring item", async () => {
    const user = userEvent.setup();
    vi.mocked(getTodoListsMock).mockResolvedValue([EMPTY_LIST]);
    vi.mocked(addTodoItemMock).mockResolvedValue({
      id: 1,
      title: "Lekarstwa",
      completed: false,
      dueAt: null,
      recurrence: "daily",
    });

    renderTodoPage();
    await screen.findByText("Zakupy");

    await user.type(screen.getByLabelText(/add item to/i), "Lekarstwa");
    await user.selectOptions(screen.getByLabelText(/repeats/i), "daily");
    await user.click(screen.getByRole("button", { name: /^add$/i }));

    await waitFor(() =>
      expect(addTodoItemMock).toHaveBeenCalledWith(1, "Lekarstwa", undefined, "daily"),
    );
  });

  it("shows a Repeats badge for a recurring item", async () => {
    vi.mocked(getTodoListsMock).mockResolvedValue([
      {
        id: 1,
        name: "Zakupy",
        items: [{ id: 2, title: "Lekarstwa", completed: false, dueAt: null, recurrence: "weekly" }],
      },
    ]);

    renderTodoPage();
    await screen.findByText("Lekarstwa");

    expect(screen.getByText(/repeats weekly/i)).toBeInTheDocument();
  });

  it("does not show a Repeats badge for a one-off item", async () => {
    vi.mocked(getTodoListsMock).mockResolvedValue([LIST_WITH_ITEM]);

    renderTodoPage();
    await screen.findByText("Mleko");

    expect(screen.queryByText(/repeats (daily|weekly)/i)).not.toBeInTheDocument();
  });

  it("sets recurrence on an existing item", async () => {
    const user = userEvent.setup();
    vi.mocked(getTodoListsMock).mockResolvedValue([LIST_WITH_ITEM]);
    vi.mocked(setTodoItemRecurrenceMock).mockResolvedValue({
      id: 1,
      title: "Mleko",
      completed: false,
      dueAt: null,
      recurrence: "weekly",
    });

    renderTodoPage();
    await screen.findByText("Mleko");

    await user.click(screen.getByRole("button", { name: /set recurrence/i }));
    await user.selectOptions(
      screen.getByRole("combobox", { name: /set recurrence/i }),
      "weekly",
    );
    await user.click(screen.getByRole("button", { name: /save recurrence/i }));

    await waitFor(() =>
      expect(setTodoItemRecurrenceMock).toHaveBeenCalledWith(1, "weekly"),
    );
  });

  it("clears recurrence on an existing item", async () => {
    const user = userEvent.setup();
    vi.mocked(getTodoListsMock).mockResolvedValue([
      {
        id: 1,
        name: "Zakupy",
        items: [{ id: 1, title: "Lekarstwa", completed: false, dueAt: null, recurrence: "daily" }],
      },
    ]);
    vi.mocked(setTodoItemRecurrenceMock).mockResolvedValue({
      id: 1,
      title: "Lekarstwa",
      completed: false,
      dueAt: null,
      recurrence: null,
    });

    renderTodoPage();
    await screen.findByText("Lekarstwa");

    await user.click(screen.getByRole("button", { name: /set recurrence/i }));
    await user.click(screen.getByRole("button", { name: /clear recurrence/i }));

    await waitFor(() => expect(setTodoItemRecurrenceMock).toHaveBeenCalledWith(1, null));
  });
});

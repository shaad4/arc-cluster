import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AutoRecovery } from "./AutoRecovery";
import type { RecoveryStatus } from "../lib/types";
const snapshot: RecoveryStatus = {
  approved: true,
  configuration: {
    enabled: false,
    interval: 30,
    max_retries: 3,
    nodes: { box2: false },
  },
  configuration_error: null,
  nodes: [
    {
      node_id: "box2",
      enabled: false,
      state: "worker_stopped",
      message: "Ray worker stopped",
      checked_at: null,
      supervisor: {
        approved: true,
        enabled: false,
        state: "recovery_failed",
        message: "Failed",
        attempts: 2,
        last_attempt: 1000,
        last_result: "recovery_failed",
        next_attempt: 2000,
        lease_expires: null,
        manual_hold: false,
      },
    },
  ],
};
function renderSection() {
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <AutoRecovery />
    </QueryClientProvider>,
  );
}
afterEach(() => vi.restoreAllMocks());
describe("Auto Recovery controls", () => {
  it("requires confirmation before enabling and renders failure status", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async () => new Response(JSON.stringify(snapshot)));
    renderSection();
    await screen.findByLabelText("Enable automatic recovery");
    expect(screen.getByText("Ray worker stopped")).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText("Enable automatic recovery"));
    await userEvent.click(screen.getByLabelText("Enable box2 recovery"));
    await userEvent.click(
      screen.getByRole("button", { name: "Save recovery settings" }),
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.filter(([, options]) => options?.method === "PATCH"),
    ).toHaveLength(0);
    await userEvent.click(
      screen.getByRole("button", { name: "Confirm recovery settings" }),
    );
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([, options]) => options?.method === "PATCH"),
      ).toBe(true),
    );
    const body = fetchMock.mock.calls.find(
      ([, options]) => options?.method === "PATCH",
    )?.[1]?.body;
    expect(JSON.parse(String(body))).toMatchObject({
      enabled: true,
      confirmed: true,
      nodes: { box2: true },
    });
  });
  it("disables enable controls without server approval", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      async () =>
        new Response(JSON.stringify({ ...snapshot, approved: false })),
    );
    renderSection();
    expect(
      await screen.findByLabelText("Enable automatic recovery"),
    ).toBeDisabled();
    expect(screen.getByLabelText("Enable box2 recovery")).toBeDisabled();
  });
  it("requires confirmation before resetting the retry budget", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async () => new Response(JSON.stringify(snapshot)));
    renderSection();
    await userEvent.click(
      await screen.findByRole("button", { name: "Reset budget" }),
    );
    expect(screen.getByRole("dialog")).toHaveTextContent(
      "intentional-stop hold",
    );
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(
      fetchMock.mock.calls.some(([, options]) => options?.method === "POST"),
    ).toBe(false);
  });
});

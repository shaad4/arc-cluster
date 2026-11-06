import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { NodeControls } from "./Nodes";
import type { Node } from "../lib/types";
const node: Node = {
  id: "box2",
  name: "box2",
  role: "worker",
  ip: "100.124.19.50",
  machine_status: "online",
  ray_status: "dead",
  status: "degraded",
  ray_id: null,
  resources: {},
  metrics: null,
  last_seen: null,
  stale: true,
  source: null,
  agent_status: "online",
  ray_process: null,
  control_reason: "Check safety first",
};
describe("worker confirmation", () => {
  it("requires a safety check and explicit dialog confirmation", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(
          JSON.stringify({
            allowed: true,
            reason: "Safe",
            member: false,
            ray_process: false,
          }),
          { status: 200 },
        ),
      );
    render(
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <NodeControls node={node} />
      </QueryClientProvider>,
    );
    expect(
      screen.getByRole("button", { name: "Recover worker" }),
    ).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Check safety" }));
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Recover worker" }),
      ).toBeEnabled(),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Recover worker" }),
    );
    expect(screen.getByRole("dialog")).toHaveTextContent("recover box2?");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    fetchMock.mockRestore();
  });
});

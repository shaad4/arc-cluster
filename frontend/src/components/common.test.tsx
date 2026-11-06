import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { ErrorState, Loading, Status } from "./common";
import { NodeTable } from "./NodeTable";
import type { Node } from "../lib/types";
describe("observation states", () => {
  it("announces loading and errors", () => {
    const view = render(<Loading />);
    expect(screen.getByRole("status")).toBeInTheDocument();
    view.rerender(<ErrorState error={new Error("Ray unreachable")} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Ray unreachable");
  });
  it("renders offline status explicitly", () => {
    render(<Status value="offline" />);
    expect(screen.getByText("offline")).toBeInTheDocument();
  });
  it("does not replace missing node measurements with zero", () => {
    const node: Node = {
      id: "box2",
      name: "box2",
      role: "worker",
      ip: "100.124.19.50",
      machine_status: "unknown",
      ray_status: "dead",
      status: "unknown",
      ray_id: null,
      resources: {},
      metrics: null,
      last_seen: null,
      stale: true,
      source: null,
      agent_status: "not configured",
      ray_process: null,
      control_reason: "Unavailable",
    };
    render(
      <MemoryRouter>
        <NodeTable nodes={[node]} />
      </MemoryRouter>,
    );
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(screen.queryByText("0.0%")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View box2" })).toHaveAttribute(
      "href",
      "/nodes/box2",
    );
  });
});

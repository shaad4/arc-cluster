import { useApi } from "../lib/api";
import type { Ray } from "../lib/types";
import { bytes, number } from "../lib/utils";
import {
  Empty,
  ErrorState,
  Loading,
  Metric,
  PageHeading,
  Panel,
  Status,
} from "../components/common";
export function RayPage() {
  const query = useApi<Ray>("/ray/status");
  if (query.isPending) return <Loading />;
  if (query.error)
    return (
      <ErrorState error={query.error} retry={() => void query.refetch()} />
    );
  const r = query.data,
    taskCount = (state: string) =>
      r.tasks.error
        ? null
        : r.tasks.items.filter((t) => String(t.state).includes(state)).length;
  return (
    <>
      <PageHeading
        title="Ray Cluster"
        description="Logical scheduling resources, tasks, and actors."
      >
        <Status value={r.available ? "online" : "unavailable"} />
      </PageHeading>
      {r.error && (
        <div className="notice">
          {r.error}. Physical machine observations remain available
          independently.
        </div>
      )}
      <div className="metric-grid">
        <Metric
          label="Live Ray nodes"
          value={r.available ? r.nodes.filter((n) => n.alive).length : "—"}
          detail={`Ray ${r.version ?? "version unavailable"}`}
        />
        <Metric
          label="Total CPU resources"
          value={number(r.available ? r.total.CPU : null)}
          detail={`${number(r.available ? (r.free.CPU ?? 0) : null)} available`}
        />
        <Metric
          label="Allocated CPUs"
          value={number(
            r.available ? (r.total.CPU ?? 0) - (r.free.CPU ?? 0) : null,
          )}
          detail="Logical allocation, not CPU utilization"
        />
        <Metric
          label="Object-store capacity"
          value={bytes(r.available ? r.total.object_store_memory : null)}
          detail="Distributed across independent nodes"
        />
      </div>
      <div className="metric-grid">
        <Metric label="Running tasks" value={number(taskCount("RUNNING"))} />
        <Metric label="Pending tasks" value={number(taskCount("PENDING"))} />
        <Metric label="Failed tasks" value={number(taskCount("FAILED"))} />
        <Metric
          label="Active actors"
          value={number(
            r.actors.error
              ? null
              : r.actors.items.filter((a) => a.state === "ALIVE").length,
          )}
        />
      </div>
      {(r.tasks.error || r.actors.error) && (
        <div className="notice">
          {r.tasks.error ?? r.actors.error}. Incomplete State API output is not
          counted as zero.
        </div>
      )}
      <Panel
        title="Ray membership"
        subtitle="Includes historical dead registrations; one machine can have multiple Ray node IDs."
      >
        {r.nodes.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Node ID</th>
                  <th>Address</th>
                  <th>Membership</th>
                  <th>CPU resources</th>
                  <th>Memory resource</th>
                  <th>Object store</th>
                </tr>
              </thead>
              <tbody>
                {r.nodes.map((n) => (
                  <tr key={n.id}>
                    <td className="mono" title={n.id}>
                      {n.id.slice(0, 16)}…
                    </td>
                    <td className="mono">{n.ip}</td>
                    <td>
                      <Status value={n.alive ? "alive" : "dead"} />
                    </td>
                    <td className="mono">{number(n.resources.CPU)}</td>
                    <td className="mono">{bytes(n.resources.memory)}</td>
                    <td className="mono">
                      {bytes(n.resources.object_store_memory)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty title="No Ray membership available" />
        )}
      </Panel>
      <div className="detail-grid">
        <Panel
          title="Recent tasks"
          subtitle="State API observation, capped at 1,000 records"
        >
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Task</th>
                  <th>State</th>
                </tr>
              </thead>
              <tbody>
                {r.tasks.items.slice(0, 30).map((t, i) => (
                  <tr key={i}>
                    <td className="mono">
                      {String(t.name ?? t.task_id ?? "Unnamed").slice(0, 50)}
                    </td>
                    <td>
                      <Status value={String(t.state)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!r.tasks.items.length && <Empty title="No task observations" />}
          </div>
        </Panel>
        <Panel
          title="Actors"
          subtitle="Persistent Ray actors are separate from Ray Jobs"
        >
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Actor</th>
                  <th>State</th>
                </tr>
              </thead>
              <tbody>
                {r.actors.items.slice(0, 30).map((a, i) => (
                  <tr key={i}>
                    <td className="mono">
                      {String(a.name || a.class_name || a.actor_id).slice(
                        0,
                        50,
                      )}
                    </td>
                    <td>
                      <Status value={String(a.state)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!r.actors.items.length && <Empty title="No actor observations" />}
          </div>
        </Panel>
      </div>
    </>
  );
}

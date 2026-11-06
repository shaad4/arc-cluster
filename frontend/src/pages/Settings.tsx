import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, useApi } from "../lib/api";
import type { Settings } from "../lib/types";
import {
  ErrorState,
  Loading,
  PageHeading,
  Panel,
  Status,
} from "../components/common";
import { Button } from "../components/ui/button";
function PollingForm({ interval }: { interval: number }) {
  const [value, setValue] = useState(interval),
    client = useQueryClient(),
    mutation = useMutation({
      mutationFn: () =>
        api("/settings", {
          method: "PATCH",
          body: JSON.stringify({ poll_interval: value }),
        }),
      onSuccess: () => void client.invalidateQueries(),
    });
  return (
    <>
      <form
        className="settings-form"
        onSubmit={(e) => {
          e.preventDefault();
          mutation.mutate();
        }}
      >
        <label htmlFor="poll-interval">Sample every</label>
        <input
          id="poll-interval"
          type="number"
          min={5}
          max={60}
          value={value}
          onChange={(e) => setValue(Number(e.target.value))}
        />
        <span className="muted">seconds</span>
        <Button
          type="submit"
          disabled={
            mutation.isPending ||
            value < 5 ||
            value > 60 ||
            !Number.isInteger(value)
          }
        >
          Save
        </Button>
        {mutation.isSuccess && (
          <span role="status">Saved for this session</span>
        )}
      </form>
      {mutation.error && <ErrorState error={mutation.error} />}
    </>
  );
}
export function SettingsPage() {
  const query = useApi<Settings>("/settings");
  if (query.isPending) return <Loading />;
  if (query.error)
    return (
      <ErrorState error={query.error} retry={() => void query.refetch()} />
    );
  const s = query.data;
  return (
    <>
      <PageHeading
        title="Settings"
        description="Control plane configuration and collection status."
      />
      <div className="detail-grid">
        <Panel title="Application">
          <dl className="definition">
            {[
              ["Cluster name", s.name],
              ["Dashboard version", s.version],
              ["Head address", s.head_address],
              ["Ray version", s.ray_version ?? "Unavailable"],
            ].map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd className="mono">{value}</dd>
              </div>
            ))}
            <div>
              <dt>Application health</dt>
              <dd>
                <Status value={s.application_health} />
              </dd>
            </div>
            <div>
              <dt>Collector</dt>
              <dd>
                <Status value={s.collector_status} />
              </dd>
            </div>
          </dl>
        </Panel>
        <Panel
          title="Collection"
          subtitle="Central sampling is shared by every browser session."
        >
          <PollingForm interval={s.poll_interval} />
          <div className="control-content">
            <p>
              Changes apply until ARC restarts. Set ARC_POLL_INTERVAL in the
              service environment to persist. Browser views refresh every 5
              seconds.
            </p>
            <p>
              Approved example workload:{" "}
              <strong>{s.approved_workload ? "Enabled" : "Disabled"}</strong>.
              Change approval only in server configuration.
            </p>
          </div>
        </Panel>
      </div>
      <Panel
        title="Node agents"
        subtitle="Credentials are read from a restricted server-side file and never returned to the browser."
      >
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Node</th>
                <th>Role</th>
                <th>Tailscale address</th>
                <th>Agent</th>
                <th>Ray process observation</th>
              </tr>
            </thead>
            <tbody>
              {s.nodes.map((n) => (
                <tr key={n.id}>
                  <td>{n.name}</td>
                  <td>{n.role}</td>
                  <td className="mono">{n.ip}</td>
                  <td>
                    <Status value={n.agent_status} />
                  </td>
                  <td>
                    {n.ray_process == null
                      ? "Unavailable"
                      : n.ray_process
                        ? "Present"
                        : "Absent"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <Panel title="Private access">
        <div className="control-content">
          <p>
            ARC listens on localhost. Connect from your laptop through an SSH
            tunnel:
          </p>
          <pre className="mono">ssh -N -L 8000:127.0.0.1:8000 box1</pre>
          <p style={{ marginTop: 14 }}>
            Open http://127.0.0.1:8000. Administrative operations are restricted
            to same-origin requests. Agent deployment and Tailscale ACL
            configuration are described in the repository documentation.
          </p>
        </div>
      </Panel>
    </>
  );
}

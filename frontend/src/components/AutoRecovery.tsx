import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, useApi } from "../lib/api";
import type { RecoveryConfiguration, RecoveryStatus } from "../lib/types";
import { time } from "../lib/utils";
import { ErrorState, Loading, Panel, Status } from "./common";
import { Button } from "./ui/button";
import { ConfirmDialog } from "./ui/dialog";

function RecoveryForm({ data }: { data: RecoveryStatus }) {
  const [draft, setDraft] = useState<RecoveryConfiguration>(data.configuration);
  const [confirm, setConfirm] = useState(false);
  const [resetNode, setResetNode] = useState<string | null>(null);
  const client = useQueryClient();
  const update = useMutation({
    mutationFn: (value: RecoveryConfiguration & { confirmed: boolean }) =>
      api<RecoveryStatus>("/recovery", {
        method: "PATCH",
        body: JSON.stringify(value),
      }),
    onSuccess: () => {
      setConfirm(false);
      void client.invalidateQueries();
    },
  });
  const reset = useMutation({
    mutationFn: (node: string) =>
      api(`/recovery/${node}/reset`, {
        method: "POST",
        body: JSON.stringify({ confirmed: true }),
      }),
    onSuccess: () => {
      setResetNode(null);
      void client.invalidateQueries();
    },
  });
  const valid =
    Number.isInteger(draft.interval) &&
    draft.interval >= 10 &&
    draft.interval <= 300 &&
    Number.isInteger(draft.max_retries) &&
    draft.max_retries >= 1 &&
    draft.max_retries <= 8;
  return (
    <>
      {!data.approved && (
        <div className="notice">
          Automatic recovery has not been approved on this server. An operator
          must configure ARC_AUTO_RECOVERY_APPROVED before it can be enabled. No
          workers will be changed.
        </div>
      )}
      {data.configuration_error && (
        <ErrorState error={new Error(data.configuration_error)} />
      )}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (draft.enabled) setConfirm(true);
          else update.mutate({ ...draft, confirmed: false });
        }}
      >
        <div className="recovery-options">
          <label className="actions">
            <input
              type="checkbox"
              aria-label="Enable automatic recovery"
              disabled={!data.approved || update.isPending}
              checked={draft.enabled}
              onChange={(event) =>
                setDraft({ ...draft, enabled: event.target.checked })
              }
            />
            Enable automatic recovery
          </label>
          <label>
            Recovery interval (seconds)
            <input
              aria-label="Recovery interval"
              type="number"
              min={10}
              max={300}
              value={draft.interval}
              onChange={(event) =>
                setDraft({ ...draft, interval: Number(event.target.value) })
              }
            />
          </label>
          <label>
            Maximum retries
            <input
              aria-label="Maximum retries"
              type="number"
              min={1}
              max={8}
              value={draft.max_retries}
              onChange={(event) =>
                setDraft({ ...draft, max_retries: Number(event.target.value) })
              }
            />
          </label>
          <Button type="submit" disabled={!valid || update.isPending}>
            Save recovery settings
          </Button>
          {data.configuration.enabled && (
            <Button
              type="button"
              variant="destructive"
              disabled={update.isPending}
              onClick={() =>
                update.mutate({
                  ...data.configuration,
                  enabled: false,
                  confirmed: false,
                })
              }
            >
              Disable now
            </Button>
          )}
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Worker</th>
                <th>Enabled</th>
                <th>Recovery state</th>
                <th>Supervisor</th>
                <th>Last attempt / result</th>
                <th>Budget</th>
              </tr>
            </thead>
            <tbody>
              {data.nodes.map((node) => (
                <tr key={node.node_id}>
                  <td>{node.node_id}</td>
                  <td>
                    <input
                      type="checkbox"
                      aria-label={`Enable ${node.node_id} recovery`}
                      disabled={!data.approved || update.isPending}
                      checked={draft.nodes[node.node_id] ?? false}
                      onChange={(event) =>
                        setDraft({
                          ...draft,
                          nodes: {
                            ...draft.nodes,
                            [node.node_id]: event.target.checked,
                          },
                        })
                      }
                    />
                  </td>
                  <td>
                    <Status value={node.state} />
                    <small className="recovery-reason">{node.message}</small>
                  </td>
                  <td>
                    <Status value={node.supervisor?.state ?? "unavailable"} />
                    <small>
                      {node.supervisor
                        ? node.supervisor.enabled
                          ? "Permission active"
                          : "No active permission"
                        : "Agent unavailable or not upgraded"}
                    </small>
                  </td>
                  <td className="mono">
                    {time(node.supervisor?.last_attempt)}
                    <small>
                      {node.supervisor?.last_result?.replaceAll("_", " ") ??
                        "No attempt recorded"}
                    </small>
                  </td>
                  <td>
                    <span className="mono">
                      {node.supervisor?.attempts ?? "—"} /{" "}
                      {data.configuration.max_retries}
                    </span>
                    <br />
                    <Button
                      type="button"
                      size="sm"
                      disabled={!node.supervisor || reset.isPending}
                      onClick={() => setResetNode(node.node_id)}
                    >
                      Reset budget
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </form>
      <div className="control-content">
        <p>
          Automatic recovery starts stopped workers. Restarting a running,
          disconnected worker requires complete, idle workload checks. Healthy
          workers are never restarted. Retry budgets survive agent restarts;
          five minutes of continuous health clears an incident.
        </p>
        <p>
          Disable prevents new attempts once acknowledged; unreachable workers
          stop acting when their permission expires. An operation already in
          progress may finish. Manual worker stops place automation on hold
          until you reset its budget.
        </p>
      </div>
      {update.error && <ErrorState error={update.error} />}{" "}
      {reset.error && <ErrorState error={reset.error} />}
      {update.isSuccess && (
        <p className="notice" role="status">
          Recovery settings saved.
        </p>
      )}
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title="Enable automatic worker recovery?"
        description="Approved workers may start Ray automatically. Running but disconnected workers may be restarted only after complete workload safety checks. Keep job submission quiescent during recovery; this is not an atomic scheduler drain."
      >
        <div className="actions">
          <Button onClick={() => setConfirm(false)}>Cancel</Button>
          <Button
            variant="default"
            disabled={update.isPending}
            onClick={() => update.mutate({ ...draft, confirmed: true })}
          >
            Confirm recovery settings
          </Button>
        </div>
        {update.error && <ErrorState error={update.error} />}
      </ConfirmDialog>
      <ConfirmDialog
        open={resetNode !== null}
        onOpenChange={(open) => {
          if (!open) setResetNode(null);
        }}
        title={`Reset ${resetNode ?? "worker"} recovery budget?`}
        description="This clears the retry limit and intentional-stop hold. If automatic recovery is enabled, the worker can attempt recovery again immediately."
      >
        <div className="actions">
          <Button onClick={() => setResetNode(null)}>Cancel</Button>
          <Button
            variant="destructive"
            disabled={reset.isPending}
            onClick={() => resetNode && reset.mutate(resetNode)}
          >
            Confirm budget reset
          </Button>
        </div>
        {reset.error && <ErrorState error={reset.error} />}
      </ConfirmDialog>
    </>
  );
}

export function AutoRecovery() {
  const query = useApi<RecoveryStatus>("/recovery");
  return (
    <Panel
      title="Auto Recovery"
      subtitle="Approved automation with bounded retries and independent worker safety checks."
    >
      {query.isPending ? (
        <Loading />
      ) : query.error ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : (
        <RecoveryForm
          key={JSON.stringify(query.data.configuration)}
          data={query.data}
        />
      )}
    </Panel>
  );
}

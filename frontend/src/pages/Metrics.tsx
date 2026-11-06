import { useState } from "react";
import { useApi } from "../lib/api";
import type { History, Node } from "../lib/types";
import { ErrorState, Loading, PageHeading } from "../components/common";
import { Chart } from "../components/Chart";
export function MetricsPage() {
  const [minutes, setMinutes] = useState(5),
    history = useApi<History>(`/metrics/history?minutes=${minutes}`),
    nodes = useApi<Node[]>("/cluster/nodes");
  const samples = history.data?.samples ?? [],
    aggregate = samples.map((s) => ({
      timestamp: s.aggregate.timestamp,
      cpu: s.aggregate.cpu_percent,
      memory: s.aggregate.memory_percent,
      disk: s.aggregate.disk_percent,
      sent:
        s.aggregate.net_sent_rate == null
          ? null
          : s.aggregate.net_sent_rate / 1024,
      received:
        s.aggregate.net_recv_rate == null
          ? null
          : s.aggregate.net_recv_rate / 1024,
      total: s.aggregate.ray_cpu_total,
      allocated:
        s.aggregate.ray_cpu_total == null ||
        s.aggregate.ray_cpu_available == null
          ? null
          : s.aggregate.ray_cpu_total - s.aggregate.ray_cpu_available,
      nodes: s.aggregate.active_nodes,
    })),
    lines = (nodes.data ?? []).map((n) => ({ key: n.id, label: n.name })),
    perNode = (field: "cpu_percent" | "memory_percent") =>
      samples.map((s) => ({
        timestamp: s.aggregate.timestamp,
        ...Object.fromEntries(
          (nodes.data ?? []).map((n) => [n.id, s.nodes[n.id]?.[field] ?? null]),
        ),
      }));
  return (
    <>
      <PageHeading
        title="Metrics"
        description="Real samples. One hour of in-memory history."
      >
        <select
          aria-label="Metrics time range"
          value={minutes}
          onChange={(e) => setMinutes(Number(e.target.value))}
        >
          <option value={5}>Last 5 minutes</option>
          <option value={15}>Last 15 minutes</option>
          <option value={60}>Last 1 hour</option>
        </select>
      </PageHeading>
      <div className="notice">
        Aggregate values include only fresh reporting nodes. Gaps represent
        unavailable measurements. History resets when ARC restarts; resources
        remain distributed across machines.
      </div>
      {history.error ? (
        <ErrorState
          error={history.error}
          retry={() => void history.refetch()}
        />
      ) : history.isPending ? (
        <Loading />
      ) : (
        <>
          <div className="chart-grid">
            <Chart
              title="Aggregate CPU"
              data={aggregate}
              lines={[{ key: "cpu", label: "CPU" }]}
              max={100}
            />
            <Chart
              title="Aggregate memory"
              data={aggregate}
              lines={[{ key: "memory", label: "Memory" }]}
              max={100}
            />
            <Chart
              title="CPU by node"
              data={perNode("cpu_percent")}
              lines={lines}
              max={100}
            />
            <Chart
              title="Memory by node"
              data={perNode("memory_percent")}
              lines={lines}
              max={100}
            />
            <Chart
              title="Persistent disk utilization"
              data={aggregate}
              lines={[{ key: "disk", label: "Observed storage" }]}
              max={100}
            />
            <Chart
              title="Network throughput"
              data={aggregate}
              lines={[
                { key: "sent", label: "Sent" },
                { key: "received", label: "Received" },
              ]}
              unit=" KiB/s"
            />
            <Chart
              title="Ray CPU resources"
              data={aggregate}
              lines={[
                { key: "total", label: "Total" },
                { key: "allocated", label: "Allocated" },
              ]}
              unit=""
            />
            <Chart
              title="Node availability"
              data={aggregate}
              lines={[{ key: "nodes", label: "Live Ray nodes" }]}
              unit=""
              max={5}
            />
          </div>
        </>
      )}
    </>
  );
}

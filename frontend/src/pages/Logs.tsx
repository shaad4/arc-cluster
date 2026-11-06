import { useState } from "react";
import { useSearchParams } from "react-router";
import { Copy, RefreshCw, Search } from "lucide-react";
import { useApi } from "../lib/api";
import type { LogData, Node } from "../lib/types";
import {
  Empty,
  ErrorState,
  Loading,
  PageHeading,
  Panel,
} from "../components/common";
import { Button } from "../components/ui/button";
export function LogsPage() {
  const [params] = useSearchParams(),
    [node, setNode] = useState(params.get("node") ?? "box1"),
    [source, setSource] = useState("raylet"),
    [severity, setSeverity] = useState("all"),
    [search, setSearch] = useState(""),
    [tail, setTail] = useState(true),
    [copied, setCopied] = useState("");
  const nodes = useApi<Node[]>("/cluster/nodes"),
    query = useApi<LogData>(
      `/logs?node_id=${encodeURIComponent(node)}&source=${source}`,
      true,
      tail ? 5000 : 0,
    );
  const text =
    query.data?.text
      .split("\n")
      .filter(
        (line) =>
          line.toLowerCase().includes(search.toLowerCase()) &&
          (severity === "all" || line.toLowerCase().includes(severity)),
      )
      .join("\n") ?? "";
  return (
    <>
      <PageHeading
        title="Logs"
        description="Bounded, redacted log tails from your machines."
      >
        <Button onClick={() => void query.refetch()}>
          <RefreshCw size={14} />
          Refresh
        </Button>
        <Button
          disabled={!text}
          onClick={() => {
            void navigator.clipboard.writeText(text).then(
              () => setCopied("Copied"),
              () => setCopied("Copy unavailable in this browser"),
            );
          }}
        >
          <Copy size={14} />
          {copied || "Copy lines"}
        </Button>
      </PageHeading>
      <div className="toolbar">
        <select
          aria-label="Log node"
          value={node}
          onChange={(e) => setNode(e.target.value)}
        >
          {(nodes.data ?? [{ id: "box1", name: "box1" }]).map((n) => (
            <option key={n.id} value={n.id}>
              {n.name}
            </option>
          ))}
        </select>
        <select
          aria-label="Log source"
          value={source}
          onChange={(e) => setSource(e.target.value)}
        >
          <option value="raylet">Raylet output</option>
          <option value="raylet-error">Raylet errors</option>
          <option value="events">ARC events</option>
        </select>
        <select
          aria-label="Log severity"
          value={severity}
          onChange={(e) => setSeverity(e.target.value)}
        >
          {["all", "error", "warning", "info"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <label className="search">
          <Search size={14} />
          <input
            aria-label="Search logs"
            placeholder="Search log lines…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <label className="actions muted">
          <input
            type="checkbox"
            checked={tail}
            onChange={(e) => setTail(e.target.checked)}
          />
          Live tail
        </label>
      </div>
      <Panel
        title={`${node} / ${source}`}
        subtitle="Last 500 lines · maximum 64 KiB · severity filtering matches text"
      >
        {query.isPending ? (
          <Loading />
        ) : query.error ? (
          <ErrorState error={query.error} retry={() => void query.refetch()} />
        ) : text ? (
          <pre className="log-window" aria-label="Log output">
            {text}
          </pre>
        ) : (
          <Empty
            title="No matching log lines"
            detail="Try another source or clear your filters."
          />
        )}
      </Panel>
      <div className="notice">
        Remote machine logs require its authenticated agent. Sensitive-looking
        lines are redacted; only explicitly allowlisted log sources are exposed.
      </div>
    </>
  );
}

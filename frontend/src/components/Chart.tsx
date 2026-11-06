import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Empty, Panel } from "./common";
export interface ChartLine {
  key: string;
  label: string;
  color?: string;
}
export function Chart({
  title,
  subtitle,
  data,
  lines,
  unit = "%",
  max,
}: {
  title: string;
  subtitle?: string;
  data: Record<string, number | null>[];
  lines: ChartLine[];
  unit?: string;
  max?: number;
}) {
  const populated = data.some((row) =>
    lines.some((line) => row[line.key] != null),
  );
  return (
    <Panel title={title} subtitle={subtitle}>
      <div className="chart">
        {!populated ? (
          <Empty
            title="Waiting for samples"
            detail="Only real, fresh observations are plotted."
          />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={data}
              margin={{ top: 12, right: 16, left: -12, bottom: 0 }}
            >
              <CartesianGrid
                stroke="var(--border)"
                vertical={false}
                strokeDasharray="3 3"
              />
              <XAxis
                dataKey="timestamp"
                tickFormatter={(v) =>
                  new Date(Number(v) * 1000).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                }
                stroke="var(--muted)"
                tickLine={false}
                axisLine={false}
                minTickGap={40}
                fontSize={10}
              />
              <YAxis
                domain={[0, max ?? "auto"]}
                stroke="var(--muted)"
                tickLine={false}
                axisLine={false}
                fontSize={10}
                tickFormatter={(v) => `${Number(v).toFixed(0)}${unit}`}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: 6,
                  fontSize: 12,
                }}
                labelFormatter={(v) =>
                  new Date(Number(v) * 1000).toLocaleTimeString()
                }
                formatter={(v) => `${Number(v).toFixed(1)}${unit}`}
              />
              {lines.map((line, i) => (
                <Line
                  key={line.key}
                  type="monotone"
                  dataKey={line.key}
                  name={line.label}
                  stroke={
                    line.color ??
                    ["var(--text)", "#8b8b94", "#5b9b87", "#b5a27b", "#7b91b5"][
                      i % 5
                    ]
                  }
                  strokeWidth={1.6}
                  dot={data.length < 2}
                  connectNulls={false}
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
      <div className="chart-legend">
        {lines.map((l, i) => (
          <span key={l.key}>
            <i
              style={{
                background:
                  l.color ??
                  ["var(--text)", "#8b8b94", "#5b9b87", "#b5a27b", "#7b91b5"][
                    i % 5
                  ],
              }}
            />
            {l.label}
          </span>
        ))}
      </div>
    </Panel>
  );
}

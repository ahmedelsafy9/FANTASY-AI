import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { PlayerRecord } from "@/types/api";
import { EmptyState } from "@/components/states";

interface MetricChartProps {
  player: PlayerRecord;
  metric: "total_points" | "minutes" | "ict_index" | "bps" | "xG" | "xA";
  label: string;
  color: string;
}

/**
 * The backend returns one row per player with precomputed rolling-window
 * averages (last 3 / 5 / 10 matches) — not a full per-Gameweek time series.
 * This chart is scoped to exactly that: it compares the 3/5/10-match
 * windows for one metric. If none of a metric's window columns exist for
 * this player, it renders an honest empty state instead of a chart.
 */
export function RollingWindowChart({ player, metric, label, color }: MetricChartProps) {
  const windows = [3, 5, 10] as const;
  const data = windows
    .map((w) => {
      const key = `${metric}_avg_last_${w}` as keyof PlayerRecord;
      const value = player[key];
      return typeof value === "number" ? { window: `Last ${w}`, value } : null;
    })
    .filter((d): d is { window: string; value: number } => d !== null);

  if (data.length === 0) {
    return (
      <EmptyState
        title={`${label} trend not available`}
        description="This metric isn't present for this player in the current dataset."
      />
    );
  }

  return (
    <div className="rounded-2xl border border-border-soft bg-surface p-5">
      <h4 className="mb-4 text-sm font-medium text-ink-secondary">{label} — rolling average</h4>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" vertical={false} />
          <XAxis
            dataKey="window"
            tick={{ fill: "#9AA3AE", fontSize: 12 }}
            axisLine={{ stroke: "rgba(255,255,255,0.08)" }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "#9AA3AE", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            width={32}
          />
          <Tooltip
            cursor={{ fill: "rgba(255,255,255,0.04)" }}
            contentStyle={{
              background: "#181C22",
              border: "1px solid rgba(255,255,255,0.14)",
              borderRadius: 10,
              fontSize: 12,
              color: "#F5F6F8",
            }}
          />
          <Bar dataKey="value" fill={color} radius={[6, 6, 0, 0]} maxBarSize={48} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

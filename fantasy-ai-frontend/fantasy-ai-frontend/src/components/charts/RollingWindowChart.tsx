import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { PlayerRecord } from "@/types/api";
import { EmptyState } from "@/components/states";

interface MetricChartProps {
  player: PlayerRecord;
  metric: "total_points" | "minutes" | "ict_index" | "bps" | "xG" | "xA";
  label: string;
  color: string;
}

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
    <div className="rounded-chunky-lg border border-slate-200 bg-white p-5 shadow-card">
      <h4 className="mb-4 text-xs font-black uppercase text-slate-500">{label} — Rolling Average</h4>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
          <XAxis
            dataKey="window"
            tick={{ fill: "#334155", fontSize: 11, fontWeight: 700 }}
            axisLine={{ stroke: "#CBD5E1" }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "#334155", fontSize: 11, fontWeight: 700 }}
            axisLine={false}
            tickLine={false}
            width={32}
          />
          <Tooltip
            cursor={{ fill: "rgba(15,23,42,0.04)" }}
            contentStyle={{
              background: "#FFFFFF",
              border: "1px solid #CBD5E1",
              borderRadius: 10,
              fontSize: 12,
              fontWeight: 800,
              color: "#0F172A",
              boxShadow: "0 4px 16px -2px rgba(15,23,42,0.1)",
            }}
          />
          <Bar dataKey="value" fill={color} radius={[6, 6, 0, 0]} maxBarSize={48} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

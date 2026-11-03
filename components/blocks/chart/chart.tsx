"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

// Chart switch ported from ai-components example-agent-data-analysis/chart-view.tsx, with the shadcn
// ChartContainer replaced by recharts' ResponsiveContainer so the app needs no shadcn chart wrapper.
// Series one takes the blueprint blue; the rest stay in the neutral scale so colour marks the main data only.
const COLORS = ["#0d6ea5", "#181818", "#858483", "#434343", "#cbcbcb", "#666666"];

export type ChartSpec = {
  chartType: string;
  title?: string;
  description?: string;
  xAxisKey: string;
  yAxisKeys: string[];
  xAxisLabel?: string;
  yAxisLabel?: string;
  data: Record<string, unknown>[];
};

const axis = { axisLine: false, tickLine: false, tickMargin: 8, fontSize: 12 } as const;

function plot({ chartType, data, xAxisKey, yAxisKeys }: ChartSpec) {
  const xKey = data.some((p) => xAxisKey in p) ? xAxisKey : "bin";
  switch (chartType) {
    case "line":
      return (
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey={xKey} {...axis} />
          <YAxis {...axis} />
          <Tooltip />
          <Legend />
          {yAxisKeys.map((k, i) => (
            <Line connectNulls dataKey={k} dot={false} isAnimationActive={false} key={k} stroke={COLORS[i % COLORS.length]} strokeWidth={2} />
          ))}
        </LineChart>
      );
    case "area":
      return (
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey={xKey} {...axis} />
          <YAxis {...axis} />
          <Tooltip />
          <Legend />
          {yAxisKeys.map((k, i) => (
            <Area connectNulls dataKey={k} isAnimationActive={false} fill={COLORS[i % COLORS.length]} fillOpacity={0.2} key={k} stroke={COLORS[i % COLORS.length]} />
          ))}
        </AreaChart>
      );
    case "scatter":
      return (
        <ScatterChart>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey={xKey} name={xKey} type="number" {...axis} />
          <YAxis dataKey={yAxisKeys[0]} name={yAxisKeys[0]} type="number" {...axis} />
          <Tooltip cursor={{ strokeDasharray: "3 3" }} />
          <Scatter isAnimationActive={false} data={data} fill={COLORS[1]} />
        </ScatterChart>
      );
    case "pie":
      return (
        <PieChart>
          <Tooltip />
          <Legend />
          <Pie isAnimationActive={false} data={data} dataKey="value" label nameKey="name" outerRadius="75%">
            {data.map((_, i) => (
              <Cell fill={COLORS[i % COLORS.length]} key={i} />
            ))}
          </Pie>
        </PieChart>
      );
    default:
      return (
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey={xKey} {...axis} />
          <YAxis {...axis} />
          <Tooltip />
          <Legend />
          {yAxisKeys.map((k, i) => (
            <Bar dataKey={k} isAnimationActive={false} fill={COLORS[i % COLORS.length]} key={k} radius={[4, 4, 0, 0]} />
          ))}
        </BarChart>
      );
  }
}

export function ChartView({ spec }: { spec: ChartSpec }) {
  if (!spec.data.length) return <p className="text-sm text-muted-foreground">No data to display.</p>;
  return (
    <div className="space-y-3 rounded-lg border border-dotted p-4">
      <div>
        <h4 className="text-sm font-medium">{spec.title}</h4>
        {spec.description ? <p className="text-xs text-muted-foreground">{spec.description}</p> : null}
      </div>
      <div className="h-[300px] w-full rounded-lg border border-dotted bg-muted/30 p-3">
        <ResponsiveContainer height="100%" width="100%">
          {plot(spec)}
        </ResponsiveContainer>
      </div>
      {spec.xAxisLabel || spec.yAxisLabel ? (
        <p className="text-xs text-muted-foreground">
          x: {spec.xAxisLabel ?? spec.xAxisKey} · y: {spec.yAxisLabel ?? spec.yAxisKeys.join(", ")}
        </p>
      ) : null}
    </div>
  );
}

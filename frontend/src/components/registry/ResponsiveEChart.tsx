"use client";

import {
  useCallback,
  useEffect,
  useRef,
  type ComponentProps,
} from "react";
import ReactECharts from "echarts-for-react";
import type { EChartsType } from "echarts";

type ResponsiveEChartProps = ComponentProps<typeof ReactECharts>;

/**
 * ECharts listens to window resizes, but the app also resizes its canvas when
 * the chat column opens. Observe the actual host so charts follow grid/card
 * transitions without retaining their mount-time width.
 */
export function ResponsiveEChart({
  className,
  style,
  onChartReady,
  ...props
}: ResponsiveEChartProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<EChartsType | null>(null);
  const frameRef = useRef(0);

  const resize = useCallback(() => {
    const host = hostRef.current;
    const chart = chartRef.current;
    if (!host || !chart || host.clientWidth <= 0) return;
    chart.resize({ width: host.clientWidth });
  }, []);

  const handleReady = useCallback(
    (chart: EChartsType) => {
      chartRef.current = chart;
      onChartReady?.(chart);
      frameRef.current = requestAnimationFrame(resize);
    },
    [onChartReady, resize],
  );

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(frameRef.current);
      frameRef.current = requestAnimationFrame(resize);
    });
    observer.observe(host);
    return () => {
      cancelAnimationFrame(frameRef.current);
      observer.disconnect();
      chartRef.current = null;
    };
  }, [resize]);

  return (
    <div
      ref={hostRef}
      className="w-full min-w-0 max-w-full overflow-hidden"
    >
      <ReactECharts
        {...props}
        className={["w-full min-w-0 max-w-full", className]
          .filter(Boolean)
          .join(" ")}
        style={{ width: "100%", minWidth: 0, ...style }}
        onChartReady={handleReady}
      />
    </div>
  );
}

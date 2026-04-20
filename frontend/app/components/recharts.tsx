"use client";

import dynamic from "next/dynamic";
import type { ComponentType } from "react";

const loadChart = (name: string) =>
  dynamic(async () => {
    const mod = await import("recharts");
    return mod[name as keyof typeof mod] as ComponentType<Record<string, unknown>>;
  }, { ssr: false }) as ComponentType<Record<string, unknown>>;

export const ResponsiveContainer = loadChart("ResponsiveContainer");
export const AreaChart = loadChart("AreaChart");
export const Area = loadChart("Area");
export const BarChart = loadChart("BarChart");
export const Bar = loadChart("Bar");
export const ComposedChart = loadChart("ComposedChart");
export const Line = loadChart("Line");
export const CartesianGrid = loadChart("CartesianGrid");
export const XAxis = loadChart("XAxis");
export const YAxis = loadChart("YAxis");
export const Tooltip = loadChart("Tooltip");
export const ReferenceLine = loadChart("ReferenceLine");

import {
  Cloud,
  CloudFog,
  CloudLightning,
  CloudRain,
  CloudSnow,
  CloudSun,
  Sun,
  type Icon,
} from "@phosphor-icons/react";
import { formatNumber } from "@/lib/format";
import type { WeatherUnitProps } from "./WeatherUnit.schema";
import { weatherKind, type WeatherKind } from "./weather-kind";

const KIND_ICON: Record<WeatherKind, Icon> = {
  clear: Sun,
  partly: CloudSun,
  overcast: Cloud,
  fog: CloudFog,
  rain: CloudRain,
  snow: CloudSnow,
  storm: CloudLightning,
};

const KIND_LABEL: Record<WeatherKind, string> = {
  clear: "Despejado",
  partly: "Parcialmente nublado",
  overcast: "Nublado",
  fog: "Niebla",
  rain: "Lluvia",
  snow: "Nieve",
  storm: "Tormenta",
};

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const n = Number(value.replace(",", "."));
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function asText(value: unknown): string {
  if (typeof value === "string") return value.trim();
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return "";
}

function formatTemp(value: unknown): string | null {
  const n = asNumber(value);
  if (n == null) return null;
  return `${formatNumber(n)}°`;
}

function formatDay(value: string, compact: boolean): string {
  const iso = value.slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return value;
  const [year, month, day] = iso.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.toLocaleDateString("es-AR", {
    weekday: compact ? "short" : "long",
    day: "numeric",
    month: compact ? "short" : "long",
    year: compact ? undefined : "numeric",
    timeZone: "UTC",
  });
}

function DayCard({
  row,
  featured,
}: {
  row: Record<string, unknown>;
  featured: boolean;
}) {
  const kind = weatherKind({
    weatherCode: row.weather_code,
    precipitation: row.precipitacion,
  });
  const Glyph = KIND_ICON[kind];
  const temp = formatTemp(row.temperatura);
  const tmin = formatTemp(row.tmin);
  const tmax = formatTemp(row.tmax);
  const rain = asNumber(row.precipitacion);
  const place = asText(row.provincia);
  const date = asText(row.fecha).slice(0, 10);

  return (
    <div
      className={[
        "rounded-xl bg-card ring-1 ring-border/80",
        featured ? "flex items-center gap-6 p-5" : "flex flex-col gap-2 p-3.5",
      ].join(" ")}
    >
      <span
        className={[
          "flex shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent",
          featured ? "h-16 w-16" : "h-10 w-10",
        ].join(" ")}
      >
        <Glyph size={featured ? 32 : 20} weight="regular" aria-hidden />
      </span>
      <div className="min-w-0">
        {temp ? (
          <p
            className={[
              "font-display font-semibold tracking-tight tabular-nums text-foreground",
              featured ? "text-5xl" : "text-2xl",
            ].join(" ")}
          >
            {temp}
            <span className="ml-1 font-sans text-base font-normal text-muted-foreground">
              C
            </span>
          </p>
        ) : null}
        <p className={featured ? "mt-1 text-sm text-muted-foreground" : "text-xs text-muted-foreground"}>
          {KIND_LABEL[kind]}
        </p>
        {place || date ? (
          <p className="mt-0.5 text-xs text-foreground/80">
            {[place, date ? formatDay(date, !featured) : ""]
              .filter(Boolean)
              .join(" · ")}
          </p>
        ) : null}
        {featured && (tmin || tmax || rain != null) ? (
          <p className="mt-2 text-sm tabular-nums text-muted-foreground">
            {[
              tmin && `mín ${tmin}`,
              tmax && `máx ${tmax}`,
              rain != null && `${formatNumber(rain)} mm`,
            ]
              .filter(Boolean)
              .join("  ·  ")}
          </p>
        ) : null}
        {!featured && (tmin || tmax) ? (
          <p className="mt-1 text-xs tabular-nums text-muted-foreground">
            {[tmin && `${tmin} mín`, tmax && `${tmax} máx`]
              .filter(Boolean)
              .join(" · ")}
          </p>
        ) : null}
      </div>
    </div>
  );
}

/** Open-Meteo rows as weather cards. One day → featured; several → a grid. */
export function WeatherUnit({ data }: WeatherUnitProps) {
  const rows = data ?? [];
  if (rows.length === 0) {
    return (
      <div className="flex h-24 items-center justify-center border-t border-rule">
        <p className="text-xs text-muted-foreground/50 select-none">Sin datos</p>
      </div>
    );
  }

  const featured = rows.length === 1;
  return (
    <div className="border-t border-rule pt-4">
      {featured ? (
        <DayCard row={rows[0]} featured />
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {rows.map((row, i) => (
            <DayCard
              key={`${asText(row.fecha)}-${asText(row.provincia)}-${i}`}
              row={row}
              featured={false}
            />
          ))}
        </div>
      )}
    </div>
  );
}

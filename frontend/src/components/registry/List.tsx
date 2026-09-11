import type { ListProps } from "./List.schema";

/**
 * List widget — compact table for structured records that don't fit Chart
 * (no numeric time series), Metric (not a single value), or PersonCard (not
 * people): legislative actas, sessions, generic list-of-records data.
 *
 * `columns` picks + labels which fields to show, in order. `data` rows are
 * injected by bind_data — the LLM only ever emits a dataRef.
 */
function formatCell(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Sí" : "No";
  return String(value);
}

export function List({ columns, data }: ListProps) {
  if (!columns || columns.length === 0) return null;

  if (!data || data.length === 0) {
    return (
      <div className="flex h-24 items-center justify-center border-t border-rule">
        <p className="text-xs text-muted-foreground/50 select-none">Sin datos</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto border-t border-rule pt-4">
      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-rule">
            {columns.map((col) => (
              <th
                key={col.key}
                scope="col"
                className="whitespace-nowrap pb-2 pr-4 font-display text-xs font-semibold uppercase tracking-wide text-muted-foreground"
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i} className="border-b border-rule/60 last:border-0">
              {columns.map((col) => (
                <td key={col.key} className="py-2 pr-4 align-top text-foreground">
                  {formatCell(row[col.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

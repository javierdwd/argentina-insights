/**
 * Approximate province centroids (lat, lon) for bubble overlays on the
 * Argentina outline map. Keys are normalized lowercase without accents.
 */
export const PROVINCE_CENTROIDS: Record<string, [number, number]> = {
  "buenos aires": [-36.7, -60.3],
  "ciudad autonoma de buenos aires": [-34.6, -58.4],
  caba: [-34.6, -58.4],
  "capital federal": [-34.6, -58.4],
  catamarca: [-28.5, -65.8],
  chaco: [-26.4, -60.9],
  chubut: [-43.8, -68.9],
  cordoba: [-32.0, -64.2],
  corrientes: [-28.7, -57.8],
  "entre rios": [-32.0, -59.2],
  formosa: [-24.9, -59.9],
  jujuy: [-23.8, -65.7],
  "la pampa": [-37.0, -65.0],
  "la rioja": [-29.4, -66.9],
  mendoza: [-34.6, -68.6],
  misiones: [-26.9, -54.5],
  neuquen: [-38.9, -69.2],
  "rio negro": [-40.7, -66.0],
  salta: [-24.8, -65.4],
  "san juan": [-31.5, -68.5],
  "san luis": [-33.3, -66.3],
  "santa cruz": [-48.7, -69.4],
  "santa fe": [-31.6, -60.7],
  "santiago del estero": [-27.8, -63.3],
  "tierra del fuego": [-54.3, -67.0],
  "tierra del fuego antartida e islas del atlantico sur": [-54.3, -67.0],
  tucuman: [-27.0, -65.4],
};

export function normalizeProvinceName(name: string): string {
  return name
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function provinceCentroid(
  name: string,
): [number, number] | undefined {
  const key = normalizeProvinceName(name);
  if (PROVINCE_CENTROIDS[key]) return PROVINCE_CENTROIDS[key];
  // Partial match (e.g. long Tierra del Fuego official name).
  for (const [k, v] of Object.entries(PROVINCE_CENTROIDS)) {
    if (key.includes(k) || k.includes(key)) return v;
  }
  return undefined;
}

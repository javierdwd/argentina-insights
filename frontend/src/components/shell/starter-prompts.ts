/**
 * Default conversation starters — Cruce is the product hook; Economía /
 * Política / Histórico / Cine are short onboarding ramps.
 *
 * `preview` hints which canvas widget the first answer usually opens —
 * used only for the starter row icon, not sent to the agent.
 */

export type StarterTopic =
  | "economia"
  | "politica"
  | "cruce"
  | "historico"
  | "cine";

/** Primary widget the first turn tends to draw. */
export type StarterPreview =
  | "bars"
  | "line"
  | "metrics"
  | "people"
  | "map"
  | "donut"
  | "list"
  | "timeline"
  | "text"
  | "weather";

export type StarterPrompt = {
  id: string;
  text: string;
  topic: StarterTopic;
  preview: StarterPreview;
  /** Compact label for the editorial entry; the full text is still submitted. */
  entryLabel?: string;
};

export const STARTER_PROMPTS: StarterPrompt[] = [
  // Cruce — hero section
  {
    id: "blue-por-mandato",
    text: "¿Qué mandato terminó con más tensión? Compará el cambio en reservas, riesgo país y dólar blue durante los últimos 4 gobiernos, y marcá los eventos presidenciales que coinciden con los mayores saltos",
    topic: "cruce",
    preview: "timeline",
    entryLabel: "Mandatos bajo presión",
  },
  {
    id: "blue-lineas-mandato",
    text: "Evolución del blue con una línea por mandato reciente en el mismo gráfico",
    topic: "cruce",
    preview: "line",
  },
  {
    id: "inflacion-mandatos",
    text: "Inflación interanual: compará el tramo del gobierno actual con el anterior",
    topic: "cruce",
    preview: "line",
  },
  {
    id: "riesgo-vs-confianza",
    text: "Durante 2026, ¿la confianza en el Gobierno se movió antes o después que el riesgo país y el dólar blue? Cruzá las tres series y señalá los principales eventos presidenciales",
    topic: "cruce",
    preview: "timeline",
    entryLabel: "¿La confianza anticipa al mercado?",
  },
  {
    id: "blue-dia-laboral",
    text: "Reconstruí la votación de modernización laboral del Senado: cómo votó cada bloque y provincia, y qué pasó con el blue, el MEP y el riesgo país ese día y durante la semana previa",
    topic: "cruce",
    preview: "map",
    entryLabel: "Una votación, política y mercados",
  },
  {
    id: "blue-semana-votacion",
    text: "Semana de la modernización laboral en el Senado: ¿cómo se movió el blue los 7 días previos?",
    topic: "cruce",
    preview: "line",
  },
  {
    id: "negativos-y-blue",
    text: "Quiénes votaron en contra de la modernización laboral en el Senado: listalos con bloque y provincia, y decime el blue de ese día",
    topic: "cruce",
    preview: "people",
  },
  {
    id: "presidente-al-votar",
    text: "En la modernización laboral del Senado, mapa de votos negativos por provincia y el blue de ese día",
    topic: "cruce",
    preview: "map",
  },
  {
    id: "uva-en-mandato",
    text: "¿Cómo evolucionó el UVA desde el inicio del mandato actual hasta hoy?",
    topic: "cruce",
    preview: "line",
  },
  {
    id: "confianza-vs-blue",
    text: "Cuando sube la confianza en el gobierno en 2026, ¿el blue suele bajar? Mostrame ambas series",
    topic: "cruce",
    preview: "line",
  },
  {
    id: "riesgo-pico-y-votos",
    text: "El día de máximo riesgo país en 2026, ¿había sesión en el Senado? Si sí, qué se votó",
    topic: "cruce",
    preview: "timeline",
  },
  {
    id: "margen-y-mep",
    text: "En las últimas actas del Senado con resultado cerrado, ¿cómo estaba el MEP ese mismo día?",
    topic: "cruce",
    preview: "list",
  },
  // Economía — ramp
  {
    id: "fx-spread",
    text: "¿Cuánto es el spread blue vs oficial hoy, y cómo se compara con el MEP?",
    topic: "economia",
    preview: "metrics",
  },
  {
    id: "blue-vs-inflacion",
    text: "En los últimos 12 meses, ¿el blue corrió más rápido que la inflación interanual?",
    topic: "economia",
    preview: "line",
  },
  {
    id: "uva-vs-plazofijo",
    text: "Compará el ritmo del UVA este año con las tasas de plazo fijo actuales",
    topic: "economia",
    preview: "metrics",
  },
  {
    id: "plazos-vs-inflacion",
    text: "¿Qué bancos pagan más de plazo fijo hoy y le ganan a la inflación interanual?",
    topic: "economia",
    preview: "list",
  },
  {
    id: "hipotecarios-uva-ranking",
    text: "Compará las TNA de créditos hipotecarios UVA y decime cuál es la más baja",
    topic: "economia",
    preview: "list",
  },
  {
    id: "fci-delta-historico",
    text: "Mostrame la evolución de la cuotaparte del FCI Delta Pesos Clase A en los últimos 12 meses",
    topic: "economia",
    preview: "line",
  },
  {
    id: "feriados-bancarios-anio",
    text: "Listá los feriados bancarios de este año",
    topic: "economia",
    preview: "list",
  },
  {
    id: "blue-con-eventos",
    text: "Marcá en el dólar blue los eventos presidenciales de 2024",
    topic: "cruce",
    preview: "timeline",
  },
  {
    id: "rem-vs-inflacion",
    text: "¿Cuánto se equivocó el REM en inflación mensual durante 2024?",
    topic: "economia",
    preview: "line",
  },
  {
    id: "demanda-vs-temperatura",
    text: "En los últimos 5 años, ¿cómo se movieron la demanda eléctrica y la temperatura juntas?",
    topic: "economia",
    preview: "line",
  },
  {
    id: "demanda-ola-calor",
    text: "En el verano 2024, ¿pico de demanda eléctrica y cómo estaba la temperatura ese mes?",
    topic: "cruce",
    preview: "metrics",
  },
  {
    id: "brokers-comisiones",
    text: "Compará comisiones de brokers para CEDEARs en pesos",
    topic: "economia",
    preview: "list",
  },
  {
    id: "reservas-por-mandato",
    text: "En la modernización laboral del Senado, distribución del voto y el MEP de ese día",
    topic: "cruce",
    preview: "donut",
  },
  {
    id: "emae-vs-inflacion",
    text: "Contexto de la modernización laboral y cómo se movió el blue esa semana",
    topic: "cruce",
    preview: "text",
  },
  {
    id: "clima-dia-votacion",
    text: "El día que el Senado votó la modernización laboral, ¿qué temperatura hizo en CABA?",
    topic: "cruce",
    preview: "weather",
  },
  // Histórico — Wikipedia + series. Mixed Macri / kirchnerismo / actual;
  // first two also feed the chat pills.
  {
    id: "historico-holdouts-2016",
    text: "1 de marzo de 2016 — acuerdo con los holdouts: explicá el conflicto, mostrá la ficha de Mauricio Macri y las noticias publicadas esa semana",
    topic: "historico",
    preview: "people",
  },
  {
    id: "historico-cuarentena",
    text: "20 de marzo de 2020 — inicio de la cuarentena: reconstruí el anuncio con la ficha de Alberto Fernández y noticias de esos días",
    topic: "historico",
    preview: "people",
  },
  {
    id: "historico-fmi-2018",
    text: "8 de mayo de 2018 — regreso al FMI: contexto, ficha de Mauricio Macri y cobertura periodística de la semana",
    topic: "historico",
    preview: "people",
  },
  {
    id: "historico-atentado-cfk",
    text: "1 de septiembre de 2022 — atentado a Cristina Fernández: qué ocurrió, ficha de Cristina y noticias publicadas después",
    topic: "historico",
    preview: "people",
  },
  {
    id: "historico-paso-2019",
    text: "11 de agosto de 2019 — el shock de las PASO: compará a Alberto Fernández y Mauricio Macri con sus fichas y las noticias del resultado",
    topic: "historico",
    preview: "people",
  },
  {
    id: "historico-canje-deuda",
    text: "22 de mayo de 2020 — oferta de canje de deuda: explicá la negociación, mostrá la ficha de Alberto Fernández y la cobertura de esos días",
    topic: "historico",
    preview: "people",
  },
  {
    id: "historico-asuncion-milei",
    text: "10 de diciembre de 2023 — asunción de Milei: crónica del día, ficha de Javier Milei y noticias sobre el cambio de gobierno",
    topic: "historico",
    preview: "people",
  },
  {
    id: "historico-corralito-2018",
    text: "30 de agosto de 2018 — crisis cambiaria: explicá las medidas, mostrá la ficha de Mauricio Macri y las noticias de la jornada",
    topic: "historico",
    preview: "people",
  },
  {
    id: "historico-legislativas-2017",
    text: "22 de octubre de 2017 — elecciones legislativas: claves del resultado, fichas de Mauricio Macri y Cristina Fernández, y noticias de esa noche",
    topic: "historico",
    preview: "people",
  },
  {
    id: "historico-generales-2019",
    text: "27 de octubre de 2019 — elecciones generales: contá la transición con las fichas de Alberto Fernández y Mauricio Macri y noticias del día",
    topic: "historico",
    preview: "people",
  },
  // Política — ramp. Self-contained: no "esa votación" / "tomá uno".
  {
    id: "laboral-por-bloque",
    text: "En la modernización laboral del Senado, ¿cómo se partió el voto por bloque parlamentario?",
    topic: "politica",
    preview: "donut",
  },
  {
    id: "laboral-por-provincia",
    text: "En la modernización laboral del Senado, ¿qué provincias inclinaron más al negativo?",
    topic: "politica",
    preview: "list",
  },
  {
    id: "laboral-mapa-negativos",
    text: "En la modernización laboral del Senado, mostrame en un mapa cuántos votos negativos hubo por provincia",
    topic: "politica",
    preview: "map",
  },
  {
    id: "historial-senador-sf",
    text: "Listá los senadores de Santa Fe y mostrá el historial de votos del primero en el mandato actual",
    topic: "politica",
    preview: "people",
  },
  // Cine — TMDB Argentine cinema only (origin AR).
  {
    id: "cine-descubrir",
    text: "Mostrame películas argentinas populares: póster, título y rating",
    topic: "cine",
    preview: "list",
  },
  {
    id: "cine-drama-2020s",
    text: "Películas argentinas de drama de los últimos años, ordenadas por rating",
    topic: "cine",
    preview: "list",
  },
  {
    id: "cine-nueve-reinas",
    text: "Ficha de Nueve reinas: sinopsis, rating y elenco",
    topic: "cine",
    preview: "people",
  },
  {
    id: "cine-darin",
    text: "Filmografía argentina de Ricardo Darín",
    topic: "cine",
    preview: "list",
  },
  {
    id: "cine-martel",
    text: "Quién es Lucrecia Martel y qué películas argentinas dirigió",
    topic: "cine",
    preview: "people",
  },
];

/** Grid: Histórico · Cruce / Economía · Política / Cine. */
export const TOPIC_ORDER: StarterTopic[] = [
  "historico",
  "cruce",
  "economia",
  "politica",
  "cine",
];

export const TOPIC_LABEL: Record<StarterTopic, string> = {
  cruce: "Cruce",
  historico: "Histórico",
  economia: "Economía",
  politica: "Política",
  cine: "Cine",
};

export const PREVIEW_LABEL: Record<StarterPreview, string> = {
  bars: "Barras",
  line: "Líneas",
  metrics: "Indicadores",
  people: "Personas",
  map: "Mapa",
  donut: "Distribución",
  list: "Tabla",
  timeline: "Línea de tiempo",
  text: "Contexto",
  weather: "Clima",
};

const FEATURED_STARTER_IDS = new Set([
  "blue-por-mandato",
  "riesgo-vs-confianza",
  "blue-dia-laboral",
]);

/** Short, high-signal examples shown beside the primary entry input. */
export const FEATURED_STARTERS = STARTER_PROMPTS.filter((prompt) =>
  FEATURED_STARTER_IDS.has(prompt.id),
);

/** Chat welcome pills: historico + cruce first, then economia / politica / cine. */
export function chatSuggestionPrompts(limit = 6): StarterPrompt[] {
  const historico = STARTER_PROMPTS.filter((p) => p.topic === "historico");
  const cruce = STARTER_PROMPTS.filter((p) => p.topic === "cruce");
  const economia = STARTER_PROMPTS.filter((p) => p.topic === "economia");
  const politica = STARTER_PROMPTS.filter((p) => p.topic === "politica");
  const cine = STARTER_PROMPTS.filter((p) => p.topic === "cine");
  const mixed = [
    ...historico.slice(0, 2),
    ...cruce.slice(0, Math.max(0, limit - 5)),
    ...economia.slice(0, 1),
    ...politica.slice(0, 1),
    ...cine.slice(0, 1),
  ];
  return mixed.slice(0, limit);
}

"use client";

import { useState, type FormEvent } from "react";
import { ArrowRight, MagnifyingGlass, Sparkle } from "@phosphor-icons/react";
import type { StarterPrompt } from "./starter-prompts";

interface PromptComposerProps {
  busy: boolean;
  featured: readonly StarterPrompt[];
  onSubmit: (text: string) => Promise<void>;
}

export function PromptComposer({
  busy,
  featured,
  onSubmit,
}: PromptComposerProps) {
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  const send = async (text: string) => {
    const query = text.trim();
    if (!query || busy) return;
    setError(null);
    try {
      await onSubmit(query);
      setValue("");
    } catch {
      setError("No pudimos iniciar la consulta. Probá nuevamente.");
    }
  };

  const onFormSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void send(value);
  };

  return (
    <div className="min-w-0">
      <div className="mb-5 flex items-center gap-2 text-xs font-semibold text-accent">
        <Sparkle size={15} weight="fill" aria-hidden />
        Datos públicos, conectados por IA
      </div>
      <h2 className="max-w-[12ch] font-display text-[clamp(2.5rem,6vw,5.75rem)] font-semibold leading-[0.94] tracking-[-0.055em] text-foreground">
        Entendé Argentina,
        <span className="block font-editorial font-medium tracking-[-0.035em]">
          dato a dato.
        </span>
      </h2>
      <p className="mt-5 max-w-[50ch] text-base leading-relaxed text-muted-foreground md:text-lg">
        Cruzá economía, política, historia y cultura en visualizaciones hechas
        para tu consulta.
      </p>

      <form onSubmit={onFormSubmit} className="mt-8">
        <label
          htmlFor="entry-query"
          className="mb-2 block text-sm font-medium text-foreground"
        >
          ¿Qué querés entender?
        </label>
        <div className="group flex items-center gap-3 rounded-2xl border border-border bg-card p-2 shadow-[0_20px_55px_-35px_color-mix(in_oklab,var(--accent)_55%,transparent)] transition-[border-color,box-shadow] focus-within:border-accent/60 focus-within:shadow-[0_24px_64px_-34px_color-mix(in_oklab,var(--accent)_70%,transparent)]">
          <MagnifyingGlass
            size={20}
            className="ml-2 shrink-0 text-muted-foreground transition-colors group-focus-within:text-accent"
            aria-hidden
          />
          <input
            id="entry-query"
            value={value}
            onChange={(event) => setValue(event.target.value)}
            disabled={busy}
            placeholder="Ej: ¿Qué pasó con el blue durante cada mandato?"
            className="min-w-0 flex-1 bg-transparent py-3 text-base text-foreground outline-none placeholder:text-muted-foreground/75 disabled:cursor-not-allowed"
          />
          <button
            type="submit"
            disabled={busy || !value.trim()}
            className="inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-xl bg-accent px-4 font-medium text-accent-foreground transition-[transform,opacity] hover:opacity-95 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40"
          >
            <span className="hidden sm:inline">
              {busy ? "Consultando" : "Preguntar"}
            </span>
            <ArrowRight size={17} weight="bold" aria-hidden />
          </button>
        </div>
        {error ? (
          <p className="mt-2 text-sm text-destructive" role="alert">
            {error}
          </p>
        ) : null}
      </form>

      <div className="mt-5 flex flex-wrap gap-2" aria-label="Consultas destacadas">
        {featured.map((prompt) => (
          <button
            key={prompt.id}
            type="button"
            disabled={busy}
            onClick={() => void send(prompt.text)}
            title={prompt.text}
            className="rounded-full border border-border bg-card/65 px-3 py-1.5 text-left text-xs leading-snug text-muted-foreground transition-[color,background-color,border-color,transform] hover:border-accent/35 hover:bg-accent-soft hover:text-foreground active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-45"
          >
            {prompt.entryLabel ?? prompt.text}
          </button>
        ))}
      </div>
    </div>
  );
}

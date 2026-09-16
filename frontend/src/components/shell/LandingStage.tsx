import Link from "next/link";
import { BrandMark } from "./HomeStage";
import { StarterBubbles } from "./StarterBubbles";

/** Public entry page. It deliberately does not mount the agent chat. */
export function LandingStage() {
  return (
    <main className="relative min-h-[100dvh] overflow-hidden px-5 py-5 md:px-10 md:py-6 lg:px-14">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-72 bg-[radial-gradient(ellipse_at_top_left,color-mix(in_oklab,var(--sky)_42%,transparent),transparent_68%)]"
      />
      <header className="relative">
        <Link
          href="/"
          aria-label="Argentina Insights, inicio"
          className="inline-flex items-start gap-2.5 rounded-lg transition-opacity hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
        >
          <BrandMark compact />
          <span className="min-w-0 truncate pb-[0.1em] font-display text-lg font-semibold leading-8 tracking-tight text-foreground">
            Argentina Insights
          </span>
        </Link>
      </header>
      <section className="relative mt-2 md:mt-3">
        <StarterBubbles />
      </section>
    </main>
  );
}

import type { TextProps } from "./Text.schema";

/**
 * Text widget — plain prose block matching the cold-bulletin shell.
 * No card chrome; inherits the stage's typographic rhythm.
 */
export function Text({ content, title }: TextProps) {
  return (
    <div className="border-t border-rule pt-4">
      {title ? (
        <p className="mb-2 text-sm text-muted-foreground">{title}</p>
      ) : null}
      <p className="text-base leading-relaxed text-foreground whitespace-pre-wrap">
        {content}
      </p>
    </div>
  );
}

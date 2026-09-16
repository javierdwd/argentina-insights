type ViewTransitionDocument = Document & {
  startViewTransition?: (
    update: () => void | Promise<void>,
  ) => {
    updateCallbackDone: Promise<void>;
    finished: Promise<void>;
  };
};

/** Same-document View Transition with a no-op fallback for unsupported browsers. */
export async function runViewTransition(update: () => void): Promise<void> {
  const doc = document as ViewTransitionDocument;
  if (
    !doc.startViewTransition ||
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  ) {
    update();
    return;
  }

  const transition = doc.startViewTransition(async () => {
    update();
    // Rendering is paused while the browser captures the new state, so waiting
    // for requestAnimationFrame here deadlocks until the callback times out.
    // A microtask still lets synchronous stores and queued updates settle.
    await Promise.resolve();
  });
  await transition.updateCallbackDone;
}

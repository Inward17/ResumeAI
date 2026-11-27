import { useLayoutEffect, useRef } from 'react';

/**
 * Staggered entrance when an element scrolls into view (CSS in index.css).
 * Only hides content when IntersectionObserver exists and motion is allowed,
 * so without either everything is just visible.
 */
export const useReveal = () => {
  const ref = useRef(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || !('IntersectionObserver' in window)
      || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return undefined;
    el.dataset.reveal = 'wait';
    const io = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      el.dataset.reveal = 'in';
      io.disconnect();
    }, { threshold: 0.15 });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return ref;
};

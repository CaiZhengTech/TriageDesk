"use client";

import { useEffect, useState } from "react";

/**
 * Rotating hero headline: types a phrase, holds long enough to read, deletes,
 * types the next. The thesis line always leads. Screen readers get the static
 * thesis (the animated span is aria-hidden); reduced-motion users get the
 * thesis with no cycling at all.
 */
const PHRASES = [
  "The AI never sends bad news on its own.",
  "Incoming tickets, triaged with receipts.",
  "Auto-resolve the routine. Escalate the risky.",
  "Every decision leaves auditable evidence.",
];

const TYPE_MS = 70;
const DELETE_MS = 35;
const HOLD_MS = 5200;
const GAP_MS = 750;

const LONGEST = PHRASES.reduce((a, b) => (b.length > a.length ? b : a));

export default function TypedHeadline() {
  const [text, setText] = useState(PHRASES[0]);

  useEffect(() => {
    // Reduced motion: keep the static thesis, no cycling.
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }

    // The thesis renders fully typed on load, so the cycle begins in the
    // DELETING phase — starting in the typing phase from full length would
    // increment past the completion check and never rotate (the bug Cai saw).
    let phrase = 0;
    let pos = PHRASES[0].length;
    let deleting = true;
    let timer: ReturnType<typeof setTimeout>;

    const step = () => {
      let delay: number;
      if (deleting) {
        pos -= 1;
        delay = DELETE_MS;
        if (pos === 0) {
          deleting = false;
          phrase = (phrase + 1) % PHRASES.length;
          delay = GAP_MS;
        }
      } else {
        pos += 1;
        delay = TYPE_MS;
        if (pos === PHRASES[phrase].length) {
          deleting = true;
          delay = HOLD_MS;
        }
      }
      setText(PHRASES[phrase].slice(0, pos));
      timer = setTimeout(step, delay);
    };

    timer = setTimeout(step, HOLD_MS);
    return () => clearTimeout(timer);
  }, []);

  return (
    <span className="type-wrap">
      <span className="type-ghost" aria-hidden="true">
        {LONGEST}
      </span>
      <span className="type-live" aria-hidden="true">
        {text}
        <span className="cursor">_</span>
      </span>
      <span className="sr-only">{PHRASES[0]}</span>
    </span>
  );
}

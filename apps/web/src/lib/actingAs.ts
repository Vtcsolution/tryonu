"use client";

import { useEffect, useState } from "react";

/** TryOnU team members only: which of the team's profiles their likes and
 * comments come from (null: their own account). Kept on this device. The
 * server checks the person is a team profile, and those always show the
 * "TryOnU team" badge. */
export type ActingPerson = { id: string; handle: string; name: string; avatar_url: string | null };

const KEY = "tu-acting-as";
const EVENT = "tu-acting-change";

export function getActingAs(): ActingPerson | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as ActingPerson) : null;
  } catch {
    return null;
  }
}

export function setActingAs(person: ActingPerson | null) {
  try {
    if (person) localStorage.setItem(KEY, JSON.stringify(person));
    else localStorage.removeItem(KEY);
  } catch {
    /* private mode: lasts until the page reloads */
  }
  window.dispatchEvent(new Event(EVENT));
}

/** "?as_person=<id>" for a like, or "" for my own account */
export function actingQuery(): string {
  const p = getActingAs();
  return p ? `?as_person=${encodeURIComponent(p.id)}` : "";
}

export function useActingAs(): ActingPerson | null {
  const [person, setPerson] = useState<ActingPerson | null>(null);
  useEffect(() => {
    const sync = () => setPerson(getActingAs());
    sync();
    window.addEventListener(EVENT, sync);
    return () => window.removeEventListener(EVENT, sync);
  }, []);
  return person;
}

"use client";

import { useMutation } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { ApiError } from "@/lib/api/client";
import { contact, type ContactTopic } from "@/lib/api/endpoints";
import { useSession } from "@/lib/auth/useSession";

const TOPICS: { id: ContactTopic; label: string }[] = [
  { id: "general", label: "General question" },
  { id: "tryon", label: "Try-ons, credits and payments" },
  { id: "store", label: "Selling on TryOnU (stores)" },
  { id: "developer", label: "Developer API and plugins" },
  { id: "partnership", label: "Partnerships and press" },
  { id: "privacy", label: "Privacy and my data" },
];

const field =
  "mt-1.5 w-full rounded-xl border border-line-strong bg-paper px-3.5 text-[16px] text-ink placeholder:text-faint focus:border-sage focus:outline-none focus:ring-2 focus:ring-sage/25";

export function ContactForm() {
  const { user } = useSession();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [topic, setTopic] = useState<ContactTopic>("general");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (user) {
      setName((n) => n || user.full_name || "");
      setEmail((e) => e || user.email);
    }
  }, [user]);
  useEffect(() => {
    const t = new URLSearchParams(window.location.search).get("topic") as ContactTopic | null;
    if (t && TOPICS.some((x) => x.id === t)) setTopic(t);
  }, []);

  const send = useMutation({ mutationFn: () => contact.send({ name: name.trim(), email: email.trim(), topic, message: message.trim() }) });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    send.mutate();
  };

  if (send.isSuccess) {
    return (
      <div className="py-6 text-center">
        <div className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-sage text-[26px] text-white">✓</div>
        <p className="mt-4 font-display text-[26px] text-ink">Message sent</p>
        <p className="mt-1 text-[16px] text-ink-soft">Thank you. We&apos;ll reply to {email} by email.</p>
        <button
          type="button"
          onClick={() => {
            setMessage("");
            send.reset();
          }}
          className="mt-5 text-[15px] font-semibold text-sage-deep hover:underline"
        >
          Send another message
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block text-[14.5px] font-medium text-ink">
          Your name
          <input required maxLength={120} value={name} onChange={(e) => setName(e.target.value)} className={`${field} h-12`} />
        </label>
        <label className="block text-[14.5px] font-medium text-ink">
          Your email
          <input
            required
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={`${field} h-12`}
            placeholder="you@example.com"
          />
        </label>
      </div>
      <label className="block text-[14.5px] font-medium text-ink">
        What is it about?
        <select value={topic} onChange={(e) => setTopic(e.target.value as ContactTopic)} className={`${field} h-12`}>
          {TOPICS.map((t) => (
            <option key={t.id} value={t.id}>
              {t.label}
            </option>
          ))}
        </select>
      </label>
      <label className="block text-[14.5px] font-medium text-ink">
        Message
        <textarea
          required
          minLength={10}
          maxLength={5000}
          rows={7}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          className={`${field} py-3 leading-relaxed`}
          placeholder="How can we help?"
        />
      </label>
      {send.isError && (
        <p role="alert" className="rounded-xl bg-[#a4553f]/10 px-3.5 py-2.5 text-[14.5px] text-[#a4553f]">
          {send.error instanceof ApiError
            ? send.error.status === 429
              ? "You've sent several messages already. Please wait a little and try again."
              : send.error.detail
            : "Your message couldn't be sent. Please try again."}
        </p>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
        <p className="text-[13.5px] text-muted">
          We use your details only to answer you. See our <a href="/privacy" className="text-sage-deep underline">privacy policy</a>.
        </p>
        <button
          type="submit"
          disabled={send.isPending}
          className="tu-press min-h-[50px] rounded-full bg-sage px-7 text-[16px] font-semibold text-white hover:bg-sage-deep disabled:opacity-60"
        >
          {send.isPending ? "Sending…" : "Send message"}
        </button>
      </div>
    </form>
  );
}

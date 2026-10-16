"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { CountryPicker } from "@/components/ui/CountryPicker";
import { Input } from "@/components/ui/Input";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { ApiError } from "@/lib/api/client";
import { auth, preferences } from "@/lib/api/endpoints";
import type { User } from "@/lib/api/types";
import { SESSION_QUERY_KEY } from "@/lib/auth/useSession";

const card = "rounded-[24px] border border-line bg-surface p-6 sm:p-7";

/** Your name, your email, and changing your password. Used on /account and in
 *  the admin panel's "My account" tab. */
export function AccountSettings({ user }: { user: User }) {
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <ProfileCard user={user} />
      <PasswordCard user={user} />
    </div>
  );
}

function ProfileCard({ user }: { user: User }) {
  const qc = useQueryClient();
  const [name, setName] = useState(user.full_name ?? "");
  const [saved, setSaved] = useState(false);
  const prefs = useQuery({ queryKey: ["preferences"], queryFn: preferences.get });
  const savedCountry = prefs.data?.country ?? "";
  const [country, setCountry] = useState<string | null>(null); // null: not changed here
  const shownCountry = country ?? savedCountry;
  const hint = useQuery({ queryKey: ["country-hint"], queryFn: auth.countryHint, staleTime: Infinity, retry: false });

  const nameChanged = name.trim() !== (user.full_name ?? "");
  const countryChanged = country !== null && country !== savedCountry;
  const save = useMutation({
    mutationFn: async () => {
      if (nameChanged) qc.setQueryData(SESSION_QUERY_KEY, await auth.updateProfile({ full_name: name.trim() }));
      if (countryChanged) qc.setQueryData(["preferences"], await preferences.update({ country }));
    },
    onSuccess: () => {
      setCountry(null);
      setSaved(true);
    },
  });

  return (
    <section className={card}>
      <h2 className="font-display text-[22px] text-ink">Your details</h2>
      <form
        className="mt-5 space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          setSaved(false);
          save.mutate();
        }}
      >
        <Input
          label="Your name"
          value={name}
          maxLength={255}
          autoComplete="name"
          onChange={(e) => {
            setName(e.target.value);
            setSaved(false);
          }}
        />
        <CountryPicker
          label="Your country"
          value={shownCountry}
          onChange={(c) => {
            setCountry(c);
            setSaved(false);
          }}
          suggested={hint.data?.country}
          hint="We show you shops that deliver to your country, local shops first."
        />
        <div>
          <span className="mb-1.5 block text-[14px] font-medium text-ink-soft">Email</span>
          <p className="flex h-11 items-center rounded-xl border border-line bg-paper-2/60 px-3.5 text-[15px] text-ink-soft">
            {user.email}
          </p>
          <p className="mt-1.5 text-[13.5px] text-muted">
            {user.is_admin ? "Administrator account" : "Your sign-in email"}
            {user.auth_provider === "google" ? " · signs in with Google" : ""}
          </p>
        </div>
        {save.isError && (
          <p role="alert" className="text-[14px] text-[#a4553f]">
            {save.error instanceof ApiError ? save.error.detail : "Couldn't save. Please try again."}
          </p>
        )}
        <div className="flex items-center gap-3">
          <Button type="submit" size="md" disabled={save.isPending || (!nameChanged && !countryChanged)}>
            {save.isPending ? "Saving…" : "Save"}
          </Button>
          {saved && <span className="text-[14.5px] font-medium text-sage-deep">✓ Saved</span>}
        </div>
      </form>
    </section>
  );
}

function PasswordCard({ user }: { user: User }) {
  const qc = useQueryClient();
  // accounts made with Google have no password yet: they set their first one
  const hasPassword = user.has_password !== false;
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const change = useMutation({ mutationFn: auth.changePassword });

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setDone(false);
    if (hasPassword && !current) return setError("Please type your current password.");
    if (next.length < 8) return setError("The new password needs at least 8 characters.");
    if (next !== again) return setError("The two new passwords are not the same.");
    try {
      const res = await change.mutateAsync({ current_password: hasPassword ? current : null, new_password: next });
      qc.setQueryData(SESSION_QUERY_KEY, res.user);
      setCurrent("");
      setNext("");
      setAgain("");
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't change your password. Please try again.");
    }
  };

  return (
    <section className={card}>
      <h2 className="font-display text-[22px] text-ink">{hasPassword ? "Change password" : "Set a password"}</h2>
      <p className="mt-1 text-[14.5px] text-muted">
        {hasPassword
          ? "You stay signed in here. Other phones and computers will need the new password."
          : "Then you can also sign in with your email and this password."}
      </p>
      <form onSubmit={onSubmit} className="mt-5 space-y-4" noValidate>
        {hasPassword && (
          <PasswordInput
            label="Current password"
            autoComplete="current-password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
          />
        )}
        <PasswordInput
          label="New password (at least 8 characters)"
          autoComplete="new-password"
          minLength={8}
          value={next}
          onChange={(e) => setNext(e.target.value)}
        />
        <PasswordInput
          label="Type the new password again"
          autoComplete="new-password"
          minLength={8}
          value={again}
          onChange={(e) => setAgain(e.target.value)}
        />
        {error && (
          <p role="alert" className="text-[14px] text-[#a4553f]">
            {error}
          </p>
        )}
        {done && (
          <p role="status" className="rounded-xl bg-sage-tint/60 px-3.5 py-2.5 text-[14.5px] font-medium text-ink">
            ✓ Password changed. Use the new one next time you sign in.
          </p>
        )}
        <Button type="submit" size="md" disabled={change.isPending}>
          {change.isPending ? "Changing…" : hasPassword ? "Change password" : "Set password"}
        </Button>
      </form>
    </section>
  );
}

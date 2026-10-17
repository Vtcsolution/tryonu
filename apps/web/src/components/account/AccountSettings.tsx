"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { CountryPicker } from "@/components/ui/CountryPicker";
import { Input } from "@/components/ui/Input";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { ApiError, resolveMediaUrl } from "@/lib/api/client";
import { auth, community, extension, preferences } from "@/lib/api/endpoints";
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
      <ConnectedBrowsers />
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
      <ProfilePhoto user={user} />
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

/** Browsers where a TryOnU extension is connected to this account. */
function ConnectedBrowsers() {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["extension-tokens"], queryFn: extension.list });
  const off = useMutation({
    mutationFn: extension.disconnectAll,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["extension-tokens"] }),
  });
  const rows = list.data ?? [];
  if (!list.isLoading && rows.length === 0) return null;
  return (
    <section className={card}>
      <h2 className="font-display text-[22px] text-ink">Browser extensions</h2>
      <p className="mt-1 text-[14.5px] text-muted">Browsers where a TryOnU extension is connected to your account.</p>
      <ul className="mt-4 divide-y divide-line rounded-[16px] border border-line">
        {rows.map((b) => (
          <li key={b.id} className="px-4 py-3 text-[14.5px]">
            <span className="font-medium text-ink">{b.kind === "store" ? "TryOnU for Stores" : "TryOnU – Try It On"}</span>
            <span className="text-muted">
              {b.label ? ` · ${b.label}` : ""} · connected {new Date(b.created_at).toLocaleDateString()}
              {b.last_used_at ? ` · last used ${new Date(b.last_used_at).toLocaleDateString()}` : ""}
            </span>
          </li>
        ))}
      </ul>
      <Button
        variant="outline"
        size="md"
        className="mt-4"
        disabled={off.isPending || rows.length === 0}
        onClick={() => off.mutate()}
      >
        {off.isPending ? "Disconnecting…" : "Disconnect all browsers"}
      </Button>
    </section>
  );
}

/** The profile picture people see in the community (and on the account button). */
function ProfilePhoto({ user }: { user: User }) {
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const refresh = () => {
    setError(null);
    qc.invalidateQueries({ queryKey: SESSION_QUERY_KEY });
    qc.invalidateQueries({ queryKey: ["community"] });
  };
  const upload = useMutation({
    mutationFn: (file: File) => community.uploadAvatar(file),
    onSuccess: refresh,
    onError: (err) => setError(err instanceof ApiError ? err.detail : "Couldn't upload that photo."),
  });
  const remove = useMutation({ mutationFn: community.removeAvatar, onSuccess: refresh });
  const letter = (user.full_name || user.email).trim().charAt(0).toUpperCase();
  return (
    <div className="mt-5 flex items-center gap-4">
      {user.avatar_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={resolveMediaUrl(user.avatar_url)} alt="" className="h-16 w-16 rounded-full object-cover" />
      ) : (
        <span className="grid h-16 w-16 place-items-center rounded-full bg-sage text-[26px] font-semibold text-white">{letter}</span>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <label className="tu-press inline-flex min-h-[40px] cursor-pointer items-center rounded-full border border-line-strong px-4 text-[14px] font-semibold text-ink hover:border-ink/40">
          {upload.isPending ? "Uploading…" : user.avatar_url ? "Change photo" : "Add a profile photo"}
          <input
            type="file"
            accept="image/*"
            className="sr-only"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) upload.mutate(file);
              e.target.value = "";
            }}
          />
        </label>
        {user.avatar_url && (
          <button type="button" onClick={() => remove.mutate()} disabled={remove.isPending} className="text-[14px] text-muted hover:text-[#a4553f]">
            Remove
          </button>
        )}
        {error && <span className="w-full text-[13.5px] text-[#a4553f]">{error}</span>}
      </div>
    </div>
  );
}

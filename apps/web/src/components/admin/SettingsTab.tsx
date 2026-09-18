"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { admin as adminApi } from "@/lib/api/endpoints";
import type { AdminSettingField, AdminSettingGroup, ConnectionTestResult } from "@/lib/api/types";
import { Badge, ErrorNote, SectionHeader, SmallButton, TableSkeleton, errorText, inputClass } from "./ui";

const SOURCE_LABEL: Record<AdminSettingField["source"], { text: string; tone: "good" | "neutral" | "warn" }> = {
  admin: { text: "Set in admin panel", tone: "good" },
  env: { text: "From server .env", tone: "neutral" },
  default: { text: "Default", tone: "neutral" },
};

// Switching one of these to a value in the list below needs an explicit
// confirmation: they silently change what users get or pay.
const RISKY_CHANGES: Record<string, { value: string; message: string }> = {
  PAYMENT_PROVIDER: {
    value: "mock",
    message: "Switch payments to MOCK? Every credit purchase will succeed without charging anyone.",
  },
  VIRTUAL_TRYON_PROVIDER: {
    value: "mock",
    message: "Switch try-on to MOCK? Users will get a placeholder image instead of a real render.",
  },
};

export function SettingsTab() {
  const query = useQuery({ queryKey: ["admin", "settings"], queryFn: adminApi.settings });

  return (
    <div>
      <SectionHeader
        title="Settings & API keys"
        hint="Changes go live on every server within about 15 seconds — no restart. Saved secrets are encrypted and never shown again."
      />
      <p className="mb-5 rounded-[14px] border border-line bg-paper-2 px-4 py-3 text-[12.5px] leading-relaxed text-muted">
        Database URL, SECRET_KEY, Redis, CORS and file storage can only be changed in the server&rsquo;s{" "}
        <code>.env</code>. A wrong value there could take the site down or lock every admin out, so they
        aren&rsquo;t editable from a page that depends on them.
      </p>

      {query.isLoading ? (
        <TableSkeleton />
      ) : query.isError || !query.data ? (
        <ErrorNote>{errorText(query.error, "Couldn't load settings.")}</ErrorNote>
      ) : (
        <div className="tu-stagger space-y-5">
          {query.data.groups.map((group) => (
            <SettingsGroupCard key={group.id} group={group} />
          ))}
        </div>
      )}
    </div>
  );
}

function SettingsGroupCard({ group }: { group: AdminSettingGroup }) {
  const qc = useQueryClient();
  const [pending, setPending] = useState<Record<string, string | null>>({});
  const [saved, setSaved] = useState(false);
  const [test, setTest] = useState<ConnectionTestResult | null>(null);
  const dirty = Object.keys(pending).length > 0;

  const save = useMutation({
    mutationFn: () => adminApi.updateSettings(pending),
    onSuccess: (data) => {
      qc.setQueryData(["admin", "settings"], data);
      qc.invalidateQueries({ queryKey: ["admin", "system"] });
      qc.invalidateQueries({ queryKey: ["admin", "retailers"] });
      qc.invalidateQueries({ queryKey: ["admin", "audit"] });
      setPending({});
      setTest(null);
      setSaved(true);
    },
  });

  const runTest = useMutation({
    mutationFn: () => adminApi.testConnection(group.id),
    onSuccess: setTest,
  });

  const setValue = (key: string, value: string | null) => {
    setSaved(false);
    setPending((p) => ({ ...p, [key]: value }));
  };

  const discard = (key: string) =>
    setPending((p) => {
      const next = { ...p };
      delete next[key];
      return next;
    });

  const onSave = () => {
    for (const [key, rule] of Object.entries(RISKY_CHANGES)) {
      if (pending[key] === rule.value && !window.confirm(rule.message)) return;
    }
    save.mutate();
  };

  return (
    <section className="rounded-[20px] border border-line bg-surface p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-display text-[18px] text-ink">{group.label}</h3>
        {group.testable && (
          <SmallButton disabled={runTest.isPending || dirty} onClick={() => runTest.mutate()}>
            {runTest.isPending ? "Testing…" : dirty ? "Save before testing" : "Test connection"}
          </SmallButton>
        )}
      </div>

      {test && (
        <p
          role="status"
          className={`tu-pop mt-3 rounded-[12px] border px-3 py-2 text-[12.5px] ${
            test.ok ? "border-sage/40 bg-sage-tint/30 text-sage-deep" : "border-[#c0503a]/30 bg-[#c0503a]/10 text-[#a4553f]"
          }`}
        >
          {test.ok ? "✓ " : "✕ "}
          {test.message}
        </p>
      )}
      {runTest.isError && <div className="mt-3"><ErrorNote>{errorText(runTest.error)}</ErrorNote></div>}

      <div className="mt-4 grid gap-x-6 gap-y-4 md:grid-cols-2">
        {group.fields.map((field) => (
          <SettingInput
            key={field.key}
            field={field}
            pending={pending[field.key]}
            isPending={field.key in pending}
            onChange={(v) => setValue(field.key, v)}
            onDiscard={() => discard(field.key)}
          />
        ))}
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-line pt-4">
        <SmallButton tone="primary" disabled={!dirty || save.isPending} onClick={onSave}>
          {save.isPending ? "Saving…" : "Save changes"}
        </SmallButton>
        {dirty && (
          <SmallButton disabled={save.isPending} onClick={() => setPending({})}>
            Discard
          </SmallButton>
        )}
        {saved && !dirty && <span className="tu-fade text-[12.5px] text-sage-deep">Saved — live within ~15 seconds.</span>}
        {save.isError && <ErrorNote>{errorText(save.error, "Couldn't save.")}</ErrorNote>}
      </div>
    </section>
  );
}

function SettingInput({
  field,
  pending,
  isPending,
  onChange,
  onDiscard,
}: {
  field: AdminSettingField;
  pending: string | null | undefined;
  isPending: boolean;
  onChange: (value: string | null) => void;
  onDiscard: () => void;
}) {
  const revertQueued = isPending && pending === null;
  const source = SOURCE_LABEL[field.source];
  const inputId = `setting-${field.key}`;

  let control;
  if (field.kind === "choice" || field.kind === "bool") {
    const options = field.kind === "bool" ? ["true", "false"] : field.choices;
    control = (
      <select
        id={inputId}
        value={isPending && pending !== null ? pending : (field.value ?? "")}
        disabled={revertQueued}
        onChange={(e) => onChange(e.target.value)}
        className={`${inputClass} w-full`}
      >
        {field.value === null && <option value="">Not set</option>}
        {options.map((o) => (
          <option key={o} value={o}>
            {field.kind === "bool" ? (o === "true" ? "Yes" : "No") : o}
          </option>
        ))}
      </select>
    );
  } else if (field.kind === "secret") {
    control = (
      <input
        id={inputId}
        type="password"
        autoComplete="new-password"
        value={isPending && pending !== null ? pending : ""}
        disabled={revertQueued}
        onChange={(e) => (e.target.value ? onChange(e.target.value) : onDiscard())}
        placeholder={field.is_set ? `${field.value} — type to replace` : "Not set"}
        className={`${inputClass} w-full`}
      />
    );
  } else {
    control = (
      <input
        id={inputId}
        type={field.kind === "int" ? "number" : "text"}
        value={isPending && pending !== null ? pending : (field.value ?? "")}
        disabled={revertQueued}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Not set"
        className={`${inputClass} w-full`}
      />
    );
  }

  return (
    <div>
      <div className="mb-1.5 flex flex-wrap items-center gap-2">
        <label htmlFor={inputId} className="text-[13px] font-medium text-ink">
          {field.label}
        </label>
        <Badge tone={source.tone}>{source.text}</Badge>
        {isPending && <Badge tone="warn">{revertQueued ? "Will revert to .env" : "Unsaved"}</Badge>}
      </div>
      {control}
      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
        <code className="text-[10.5px] text-faint">{field.key}</code>
        {field.source === "admin" && !isPending && (
          <button
            type="button"
            onClick={() => onChange(null)}
            className="text-[11.5px] text-muted underline-offset-2 hover:text-ink hover:underline"
          >
            Revert to .env value
          </button>
        )}
        {isPending && (
          <button
            type="button"
            onClick={onDiscard}
            className="text-[11.5px] text-muted underline-offset-2 hover:text-ink hover:underline"
          >
            Undo
          </button>
        )}
      </div>
      {field.help && <p className="mt-1 text-[11.5px] leading-snug text-muted">{field.help}</p>}
      {field.warning && <p className="mt-1 text-[11.5px] leading-snug text-[#8a6d1f]">⚠ {field.warning}</p>}
      {field.unreadable && (
        <p className="mt-1 text-[11.5px] leading-snug text-[#a4553f]">
          ⚠ The saved value can&rsquo;t be decrypted (SECRET_KEY changed) and is being ignored — enter it again.
        </p>
      )}
    </div>
  );
}

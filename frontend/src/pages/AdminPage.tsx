import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, can } from "../api/client";
import ModeTabs from "../components/ModeTabs";

type AdminTab = "overview" | "people" | "roles" | "audit";

type Cap = { id: string; label: string; privileged: boolean };
type RoleRow = {
  slug: string;
  name: string;
  description: string;
  capabilities: string[];
  statewide: boolean;
  builtin: boolean;
  user_count: number;
};
type UserRow = {
  id: number;
  username: string;
  full_name: string;
  email: string;
  role: string;
  role_name: string;
  department_id: number | null;
  department_name: string | null;
  is_active: boolean;
  capabilities: string[];
  scope: string;
};
type Dept = { id: number; code: string; name: string };

function parseTab(raw: string | null, superAdmin: boolean): AdminTab {
  if (raw === "people" || raw === "roles") return superAdmin ? raw : "overview";
  if (raw === "audit" || raw === "overview") return raw;
  return superAdmin ? "people" : "overview";
}

export default function AdminPage() {
  const superAdmin = can("manage_roles");
  const [params, setParams] = useSearchParams();
  const tab = parseTab(params.get("tab"), superAdmin);
  const [stats, setStats] = useState<Record<string, unknown>>({});
  const [audit, setAudit] = useState<Record<string, unknown>[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [catalog, setCatalog] = useState<Cap[]>([]);
  const [roles, setRoles] = useState<RoleRow[]>([]);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [depts, setDepts] = useState<Dept[]>([]);

  const [roleName, setRoleName] = useState("");
  const [roleSlug, setRoleSlug] = useState("");
  const [roleDesc, setRoleDesc] = useState("");
  const [roleCaps, setRoleCaps] = useState<string[]>(["view_live", "ack_alert"]);
  const [roleStatewide, setRoleStatewide] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);

  const [newUser, setNewUser] = useState({
    username: "",
    password: "",
    full_name: "",
    email: "",
    role: "control_room_operator",
    department_id: "",
  });

  function setTab(next: AdminTab) {
    setParams(
      (p) => {
        const copy = new URLSearchParams(p);
        copy.set("tab", next);
        return copy;
      },
      { replace: true }
    );
  }

  async function loadIam() {
    if (!superAdmin) return;
    const [cat, roleRows, userRows, deptRows] = await Promise.all([
      api<{ capabilities: Cap[] }>("/api/v1/admin/iam/catalog"),
      api<RoleRow[]>("/api/v1/admin/iam/roles"),
      api<UserRow[]>("/api/v1/admin/iam/users"),
      api<Dept[]>("/api/v1/cameras/departments"),
    ]);
    setCatalog(cat.capabilities);
    setRoles(roleRows);
    setUsers(userRows);
    setDepts(deptRows);
  }

  useEffect(() => {
    api<Record<string, unknown>>("/api/v1/admin/stats").then(setStats).catch((err) => setError(String(err)));
    api<Record<string, unknown>[]>("/api/v1/admin/audit")
      .then(setAudit)
      .catch(() => setError("Audit log requires coordinator or admin role."));
    loadIam().catch((err) => setError(String(err)));
  }, [superAdmin]);

  const assignableCaps = useMemo(() => catalog.filter((c) => !c.privileged), [catalog]);
  const customRoles = roles.filter((r) => !r.builtin);

  function toggleCap(id: string) {
    setRoleCaps((prev) => (prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]));
  }

  function startEdit(row: RoleRow) {
    setEditing(row.slug);
    setRoleName(row.name);
    setRoleSlug(row.slug);
    setRoleDesc(row.description);
    setRoleCaps(row.capabilities.filter((c) => c !== "statewide"));
    setRoleStatewide(row.statewide);
    setTab("roles");
  }

  function resetRoleForm() {
    setEditing(null);
    setRoleName("");
    setRoleSlug("");
    setRoleDesc("");
    setRoleCaps(["view_live", "ack_alert"]);
    setRoleStatewide(false);
  }

  async function saveRole(e: FormEvent) {
    e.preventDefault();
    setError("");
    setNotice("");
    const body = {
      name: roleName,
      slug: roleSlug || undefined,
      description: roleDesc,
      capabilities: roleCaps,
      statewide: roleStatewide,
    };
    try {
      if (editing) {
        await api(`/api/v1/admin/iam/roles/${editing}`, { method: "PATCH", body: JSON.stringify(body) });
        setNotice(`Updated role ${editing}`);
      } else {
        await api("/api/v1/admin/iam/roles", { method: "POST", body: JSON.stringify(body) });
        setNotice("Custom role created");
      }
      resetRoleForm();
      await loadIam();
    } catch (err) {
      setError(String(err));
    }
  }

  async function removeRole(slug: string) {
    if (!window.confirm(`Remove custom role ${slug}? Users must be reassigned first.`)) return;
    setError("");
    try {
      await api(`/api/v1/admin/iam/roles/${slug}`, { method: "DELETE" });
      setNotice(`Removed ${slug}`);
      if (editing === slug) resetRoleForm();
      await loadIam();
    } catch (err) {
      setError(String(err));
    }
  }

  async function patchUser(id: number, body: Record<string, unknown>) {
    setError("");
    setNotice("");
    try {
      await api(`/api/v1/admin/iam/users/${id}`, { method: "PATCH", body: JSON.stringify(body) });
      await loadIam();
    } catch (err) {
      setError(String(err));
    }
  }

  async function createAccount(e: FormEvent) {
    e.preventDefault();
    setError("");
    setNotice("");
    try {
      await api("/api/v1/admin/iam/users", {
        method: "POST",
        body: JSON.stringify({
          ...newUser,
          department_id: newUser.department_id ? Number(newUser.department_id) : null,
        }),
      });
      setNotice(`Created ${newUser.username}`);
      setNewUser({
        username: "",
        password: "",
        full_name: "",
        email: "",
        role: "control_room_operator",
        department_id: "",
      });
      await loadIam();
    } catch (err) {
      setError(String(err));
    }
  }

  const tabOptions = [
    { id: "overview" as const, label: "Overview" },
    ...(superAdmin
      ? [
          { id: "people" as const, label: "People" },
          { id: "roles" as const, label: "Custom roles" },
        ]
      : []),
    { id: "audit" as const, label: "Audit" },
  ];

  return (
    <div className="h-full p-4 overflow-auto">
      <div className="flex flex-col lg:flex-row lg:items-center gap-3 mb-4">
        <div>
          <h1 className="text-lg font-semibold">{superAdmin ? "Super admin" : "Administration"}</h1>
          <p className="text-[11px] text-slate-500">
            {superAdmin
              ? "Create custom roles, assign or remove them from accounts, and review the audit trail."
              : "Department stats and audit. Super-admin role assignment is limited to system administrators."}
          </p>
        </div>
        <div className="lg:ml-auto">
          <ModeTabs idPrefix="admin-tab" label="Admin section" value={tab} onChange={setTab} options={tabOptions} />
        </div>
      </div>
      {error && (
        <div className="text-red-400 text-xs mb-3" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <div className="text-emerald-400 text-xs mb-3" role="status">
          {notice}
        </div>
      )}

      {tab === "overview" && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {["cameras", "online", "events", "open_alerts"].map((k) => (
            <div key={k} className="border border-white/10 rounded p-3 bg-ink-900">
              <div className="text-[10px] uppercase tracking-widest text-slate-500">{k.replaceAll("_", " ")}</div>
              <div className="text-2xl font-semibold text-brass-400">{String(stats[k] ?? "—")}</div>
            </div>
          ))}
          {superAdmin && (
            <p className="col-span-full text-[12px] text-slate-400">
              Open <Link className="text-brass-400 underline" to="/admin?tab=people">People</Link> to assign roles, or{" "}
              <Link className="text-brass-400 underline" to="/admin?tab=roles">Custom roles</Link> to add a new one.
            </p>
          )}
        </div>
      )}

      {tab === "people" && superAdmin && (
        <div className="space-y-6">
          <form onSubmit={createAccount} className="border border-white/10 rounded p-3 bg-ink-900 grid grid-cols-1 md:grid-cols-3 gap-2">
            <h2 className="md:col-span-3 text-sm font-semibold text-brass-400">New account</h2>
            <label className="text-[11px] text-slate-400">
              Username
              <input className="mt-1 w-full bg-ink-950 border border-white/10 rounded px-2 py-1.5 text-sm" value={newUser.username} onChange={(e) => setNewUser((p) => ({ ...p, username: e.target.value }))} required />
            </label>
            <label className="text-[11px] text-slate-400">
              Password
              <input type="password" minLength={10} className="mt-1 w-full bg-ink-950 border border-white/10 rounded px-2 py-1.5 text-sm" value={newUser.password} onChange={(e) => setNewUser((p) => ({ ...p, password: e.target.value }))} required />
            </label>
            <label className="text-[11px] text-slate-400">
              Full name
              <input className="mt-1 w-full bg-ink-950 border border-white/10 rounded px-2 py-1.5 text-sm" value={newUser.full_name} onChange={(e) => setNewUser((p) => ({ ...p, full_name: e.target.value }))} required />
            </label>
            <label className="text-[11px] text-slate-400">
              Email
              <input type="email" className="mt-1 w-full bg-ink-950 border border-white/10 rounded px-2 py-1.5 text-sm" value={newUser.email} onChange={(e) => setNewUser((p) => ({ ...p, email: e.target.value }))} required />
            </label>
            <label className="text-[11px] text-slate-400">
              Role
              <select className="mt-1 w-full bg-ink-950 border border-white/10 rounded px-2 py-1.5 text-sm" value={newUser.role} onChange={(e) => setNewUser((p) => ({ ...p, role: e.target.value }))}>
                {roles.map((r) => (
                  <option key={r.slug} value={r.slug}>
                    {r.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-[11px] text-slate-400">
              Department
              <select className="mt-1 w-full bg-ink-950 border border-white/10 rounded px-2 py-1.5 text-sm" value={newUser.department_id} onChange={(e) => setNewUser((p) => ({ ...p, department_id: e.target.value }))}>
                <option value="">Statewide / none</option>
                {depts.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="md:col-span-3">
              <button type="submit" className="bg-brass-500 text-ink-950 px-3 py-1.5 rounded text-sm font-semibold">
                Create user
              </button>
            </div>
          </form>

          <div className="overflow-x-auto">
            <table className="w-full text-xs min-w-[720px]">
              <thead className="text-slate-500 uppercase">
                <tr>
                  <th className="text-left py-2">User</th>
                  <th className="text-left">Role</th>
                  <th className="text-left">Department</th>
                  <th className="text-left">Status</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-t border-white/5">
                    <td className="py-2">
                      <div className="font-medium">{u.full_name}</div>
                      <div className="text-slate-500 font-mono">{u.username}</div>
                    </td>
                    <td>
                      <select
                        aria-label={`Role for ${u.username}`}
                        className="bg-ink-950 border border-white/10 rounded px-2 py-1"
                        value={u.role}
                        onChange={(e) => patchUser(u.id, { role: e.target.value })}
                      >
                        {roles.map((r) => (
                          <option key={r.slug} value={r.slug}>
                            {r.name}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <select
                        aria-label={`Department for ${u.username}`}
                        className="bg-ink-950 border border-white/10 rounded px-2 py-1"
                        value={u.department_id ?? ""}
                        onChange={(e) => patchUser(u.id, { department_id: e.target.value ? Number(e.target.value) : null })}
                      >
                        <option value="">Statewide / none</option>
                        {depts.map((d) => (
                          <option key={d.id} value={d.id}>
                            {d.name}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <button
                        type="button"
                        className={`px-2 py-1 rounded border ${u.is_active ? "border-emerald-500/40 text-emerald-300" : "border-white/15 text-slate-500"}`}
                        onClick={() => {
                          if (u.is_active && !window.confirm(`Deactivate ${u.username}? They will be signed out immediately.`)) return;
                          patchUser(u.id, { is_active: !u.is_active });
                        }}
                      >
                        {u.is_active ? "Active" : "Disabled"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "roles" && superAdmin && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          <form onSubmit={saveRole} className="lg:col-span-5 border border-white/10 rounded p-3 bg-ink-900 space-y-2">
            <h2 className="text-sm font-semibold text-brass-400">{editing ? `Edit ${editing}` : "New custom role"}</h2>
            <label className="block text-[11px] text-slate-400">
              Display name
              <input className="mt-1 w-full bg-ink-950 border border-white/10 rounded px-2 py-1.5 text-sm" value={roleName} onChange={(e) => setRoleName(e.target.value)} required />
            </label>
            {!editing && (
              <label className="block text-[11px] text-slate-400">
                Role id (optional)
                <input className="mt-1 w-full bg-ink-950 border border-white/10 rounded px-2 py-1.5 text-sm font-mono" value={roleSlug} onChange={(e) => setRoleSlug(e.target.value)} placeholder="night_shift_lead" />
              </label>
            )}
            <label className="block text-[11px] text-slate-400">
              Description
              <textarea className="mt-1 w-full bg-ink-950 border border-white/10 rounded px-2 py-1.5 text-sm min-h-[56px]" value={roleDesc} onChange={(e) => setRoleDesc(e.target.value)} />
            </label>
            <label className="flex items-center gap-2 text-[12px] text-slate-300">
              <input type="checkbox" checked={roleStatewide} onChange={(e) => setRoleStatewide(e.target.checked)} />
              Statewide cameras (no home-department lock)
            </label>
            <fieldset className="border border-white/10 rounded p-2">
              <legend className="text-[11px] text-slate-400 px-1">Capabilities</legend>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                {assignableCaps.map((c) => (
                  <label key={c.id} className="flex items-start gap-2 text-[12px] text-slate-300">
                    <input type="checkbox" className="mt-0.5" checked={roleCaps.includes(c.id)} onChange={() => toggleCap(c.id)} />
                    <span>
                      {c.label}
                      <span className="block text-[10px] text-slate-500 font-mono">{c.id}</span>
                    </span>
                  </label>
                ))}
              </div>
              <p className="text-[10px] text-slate-500 mt-2">Super-admin actions (create users, manage roles) stay on the system administrator account only.</p>
            </fieldset>
            <div className="flex gap-2">
              <button type="submit" className="bg-brass-500 text-ink-950 px-3 py-1.5 rounded text-sm font-semibold">
                {editing ? "Save role" : "Create role"}
              </button>
              {editing && (
                <button type="button" className="text-xs px-3 py-1.5" onClick={resetRoleForm}>
                  Cancel
                </button>
              )}
            </div>
          </form>
          <div className="lg:col-span-7 space-y-2">
            <h2 className="text-sm font-semibold">Catalog</h2>
            {roles.map((r) => (
              <article key={r.slug} className="border border-white/10 rounded p-3 bg-ink-900">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-medium">{r.name}</h3>
                  <span className="font-mono text-[11px] text-slate-500">{r.slug}</span>
                  {r.builtin && <span className="text-[10px] uppercase tracking-wide text-slate-500">built-in</span>}
                  {r.statewide && <span className="text-[10px] uppercase tracking-wide text-brass-400">statewide</span>}
                  <span className="text-[11px] text-slate-500 ml-auto">{r.user_count} user{r.user_count === 1 ? "" : "s"}</span>
                </div>
                <p className="text-[11px] text-slate-400 mt-1">{r.description || r.capabilities.join(", ")}</p>
                {!r.builtin && (
                  <div className="mt-2 flex gap-2">
                    <button type="button" className="text-[11px] px-2 py-1 border border-white/15 rounded" onClick={() => startEdit(r)}>
                      Edit
                    </button>
                    <button type="button" className="text-[11px] px-2 py-1 border border-red-500/40 text-red-300 rounded" onClick={() => removeRole(r.slug)}>
                      Remove
                    </button>
                  </div>
                )}
              </article>
            ))}
            {customRoles.length === 0 && <p className="text-xs text-slate-500">No custom roles yet. Create one on the left, then assign it under People.</p>}
          </div>
        </div>
      )}

      {tab === "audit" && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs min-w-[640px]">
            <thead className="text-slate-500 uppercase">
              <tr>
                <th className="text-left py-2">Time</th>
                <th className="text-left">User</th>
                <th className="text-left">Action</th>
                <th className="text-left">Resource</th>
                <th className="text-left">IP</th>
              </tr>
            </thead>
            <tbody>
              {audit.map((r) => (
                <tr key={String(r.id)} className="border-t border-white/5">
                  <td className="py-1.5 font-mono">{String(r.created_at)}</td>
                  <td>{String(r.username)}</td>
                  <td>{String(r.action)}</td>
                  <td className="text-slate-400">{String(r.resource)}</td>
                  <td>{String(r.ip_address)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

import { FormEvent, useEffect, useState } from "react";
import { api, can } from "../api/client";

interface Entry {
  id: number;
  entity_type: string;
  category: string;
  plate_number?: string | null;
  name?: string | null;
  description?: string | null;
  priority: string;
}

export default function WatchlistPage() {
  const [rows, setRows] = useState<Entry[]>([]);
  const [plate, setPlate] = useState("");
  const [name, setName] = useState("");
  const [category, setCategory] = useState("stolen_vehicle");

  async function load() {
    setRows(await api<Entry[]>("/api/v1/watchlist"));
  }
  useEffect(() => {
    load();
  }, []);

  async function add(e: FormEvent) {
    e.preventDefault();
    await api("/api/v1/watchlist", {
      method: "POST",
      body: JSON.stringify({
        entity_type: category.includes("person") ? "person" : "vehicle",
        category,
        plate_number: plate || null,
        name,
        priority: "high",
      }),
    });
    setPlate("");
    setName("");
    load();
  }

  return (
    <div className="h-full p-4 overflow-auto">
      <h1 className="text-lg font-semibold mb-4">Watchlist</h1>
      {can("watchlist_write") ? (
      <form onSubmit={add} className="flex flex-col sm:flex-row gap-2 mb-6 text-sm">
        <select className="bg-ink-900 border border-white/10 rounded px-2 py-2" value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="stolen_vehicle">Stolen vehicle</option>
          <option value="blacklisted_vehicle">Blacklisted vehicle</option>
          <option value="wanted_person">Wanted person</option>
          <option value="missing_person">Missing person</option>
        </select>
        <input placeholder="Plate" className="bg-ink-900 border border-white/10 rounded px-2 py-1 font-mono" value={plate} onChange={(e) => setPlate(e.target.value)} />
        <input placeholder="Name / description" className="bg-ink-900 border border-white/10 rounded px-2 py-1 flex-1" value={name} onChange={(e) => setName(e.target.value)} />
        <button className="bg-brass-500 text-ink-950 px-3 rounded font-semibold">Add</button>
      </form>
      ) : (
        <p className="text-xs text-slate-500 mb-6">View only — operators cannot mutate the watchlist.</p>
      )}
      <div className="overflow-x-auto">
      <table className="w-full text-sm min-w-[560px]">
        <thead className="text-xs uppercase text-slate-500">
          <tr>
            <th className="text-left py-2">Category</th>
            <th className="text-left">Name</th>
            <th className="text-left">Plate</th>
            <th className="text-left">Priority</th>
            <th className="text-left">Notes</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-t border-white/5">
              <td className="py-2 text-brass-400">{r.category.replaceAll("_", " ")}</td>
              <td>{r.name}</td>
              <td className="font-mono">{r.plate_number}</td>
              <td>{r.priority}</td>
              <td className="text-slate-400 text-xs">{r.description}</td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </div>
  );
}

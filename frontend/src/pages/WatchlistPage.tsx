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
  has_face?: boolean;
  photo_url?: string | null;
}

export default function WatchlistPage() {
  const [rows, setRows] = useState<Entry[]>([]);
  const [plate, setPlate] = useState("");
  const [name, setName] = useState("");
  const [category, setCategory] = useState("stolen_vehicle");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState("");

  async function load() {
    setRows(await api<Entry[]>("/api/v1/watchlist"));
  }
  useEffect(() => {
    load();
  }, []);

  async function add(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
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
      await load();
    } catch (err) {
      setError(String(err));
    }
  }

  return (
    <div className="h-full p-4 overflow-auto bg-[#0B0D10]">
      <h1 className="text-lg font-semibold mb-1 text-[#F2F4F7]">Watchlist</h1>
      <p className="text-[11px] text-[#667085] mb-4">
        Enroll an adult still (ArcFace / buffalo_l). Face search is purpose-logged and runs on own/demo cameras, not official Sentinel street feeds.
      </p>
      {error && <div className="text-red-400 text-xs mb-2">{error}</div>}
      {can("watchlist_write") ? (
        <form onSubmit={add} className="flex flex-col sm:flex-row gap-2 mb-6 text-sm">
          <select
            className="bg-[#11151C] border border-white/10 rounded px-2 py-2 text-[#F2F4F7]"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="stolen_vehicle">Stolen vehicle</option>
            <option value="blacklisted_vehicle">Blacklisted vehicle</option>
            <option value="wanted_person">Wanted person</option>
            <option value="missing_person">Missing person</option>
          </select>
          <input
            placeholder="Plate"
            className="bg-[#11151C] border border-white/10 rounded px-2 py-1 font-mono text-[#F2F4F7]"
            value={plate}
            onChange={(e) => setPlate(e.target.value)}
          />
          <input
            placeholder="Name / description"
            className="bg-[#11151C] border border-white/10 rounded px-2 py-1 flex-1 text-[#F2F4F7]"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <button className="bg-[#D9A441] text-[#0B0D10] px-3 rounded font-semibold">Add</button>
        </form>
      ) : (
        <p className="text-xs text-[#667085] mb-6">View only — operators cannot mutate the watchlist.</p>
      )}
      <div className="overflow-x-auto rounded-[4px] border border-white/[0.07] bg-[#0B0F14]">
        <table className="w-full text-sm min-w-[560px]">
          <thead>
            <tr className="h-[40px] bg-[#0D1219] border-b border-white/[0.07] text-[11.5px] font-semibold tracking-wider text-[#6F7D91] uppercase">
              <th className="text-left py-2 pl-4">Category</th>
              <th className="text-left">Name</th>
              <th className="text-left">Plate</th>
              <th className="text-left">Priority</th>
              <th className="text-left">Face</th>
              <th className="text-left">Notes</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-white/[0.05] hover:bg-[#121722]">
                <td className="py-2 pl-4 text-[#D9A441]">{r.category.replaceAll("_", " ")}</td>
                <td className="text-[#F2F4F7]">{r.name}</td>
                <td className="font-mono text-[#A8B2C1]">{r.plate_number}</td>
                <td className="text-[#A8B2C1]">{r.priority}</td>
                <td className="text-xs">
                  {r.entity_type === "person" ? (
                    <div className="flex items-center gap-2">
                      <span className={r.has_face ? "text-[#D9A441]" : "text-[#667085]"}>
                        {r.has_face ? "enrolled" : "none"}
                      </span>
                      {can("watchlist_write") && (
                        <label className="text-[#E8B858] underline cursor-pointer">
                          {busyId === r.id ? "…" : "Upload"}
                          <input
                            type="file"
                            accept="image/*"
                            className="hidden"
                            disabled={busyId === r.id}
                            onChange={async (e) => {
                              const file = e.target.files?.[0];
                              e.target.value = "";
                              if (!file) return;
                              setError("");
                              setBusyId(r.id);
                              try {
                                const body = new FormData();
                                body.append("file", file);
                                await api(`/api/v1/watchlist/${r.id}/face`, { method: "POST", body });
                                await load();
                              } catch (err) {
                                setError(String(err));
                              } finally {
                                setBusyId(null);
                              }
                            }}
                          />
                        </label>
                      )}
                    </div>
                  ) : (
                    <span className="text-[#4A5568]">—</span>
                  )}
                </td>
                <td className="text-[#667085] text-xs">{r.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

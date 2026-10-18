import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, WatchGroup } from "../api";

type Props = {
  activeCode?: string;
  onSelect: (code: string) => void;
  onBatch?: (codes: string[], groupId: string) => void;
  currentStock?: { code: string; name: string; market: string } | null;
};

export default function WatchlistPanel({ activeCode, onSelect, onBatch, currentStock }: Props) {
  const [groups, setGroups] = useState<WatchGroup[]>([]);
  const [gid, setGid] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [newName, setNewName] = useState("");
  const [err, setErr] = useState("");

  const refresh = useCallback(async () => {
    try {
      const res = await api.watchlists();
      setGroups(res.groups);
      setGid((prev) => prev || res.groups[0]?.id || "");
      setErr("");
    } catch (e) {
      setErr((e as Error).message);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const group = groups.find((g) => g.id === gid) || groups[0];

  async function createGroup(e: FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    const g = await api.createWatchlist(newName.trim());
    setNewName("");
    await refresh();
    setGid(g.id);
  }

  async function addCurrent() {
    if (!currentStock || !group) return;
    await api.addWatchStocks(group.id, [currentStock]);
    await refresh();
  }

  async function removeCode(code: string) {
    if (!group) return;
    await api.removeWatchStock(group.id, code);
    setSelected((prev) => {
      const n = new Set(prev);
      n.delete(code);
      return n;
    });
    await refresh();
  }

  function toggle(code: string) {
    setSelected((prev) => {
      const n = new Set(prev);
      if (n.has(code)) n.delete(code);
      else n.add(code);
      return n;
    });
  }

  function toggleAll() {
    if (!group) return;
    const codes = group.stocks.map((s) => s.code);
    if (selected.size === codes.length) setSelected(new Set());
    else setSelected(new Set(codes));
  }

  return (
    <aside className="watch-panel">
      <div className="watch-head">
        <strong>自选分组</strong>
        <button type="button" className="text-btn" onClick={() => void refresh()}>
          刷新
        </button>
      </div>
      {err && <p className="hint error-text">{err}</p>}
      <div className="watch-groups">
        {groups.map((g) => (
          <button
            key={g.id}
            type="button"
            className={g.id === group?.id ? "chip active" : "chip"}
            onClick={() => {
              setGid(g.id);
              setSelected(new Set());
            }}
          >
            {g.name}
            <span>{g.stocks.length}</span>
          </button>
        ))}
      </div>
      <form className="watch-create" onSubmit={createGroup}>
        <input
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="新建分组名"
        />
        <button type="submit">建组</button>
      </form>
      {currentStock && (
        <button type="button" className="ghost-btn block" onClick={() => void addCurrent()}>
          + 加入「{group?.name || "自选"}」：{currentStock.name}
        </button>
      )}
      <div className="watch-tools">
        <button type="button" className="text-btn" onClick={toggleAll}>
          {selected.size && group && selected.size === group.stocks.length ? "取消全选" : "全选"}
        </button>
        <button
          type="button"
          className="primary-btn sm"
          disabled={!selected.size || !onBatch || !group}
          onClick={() => group && onBatch?.([...selected], group.id)}
        >
          批量分析 ({selected.size})
        </button>
      </div>
      <ul className="watch-list">
        {(group?.stocks || []).map((s) => (
          <li key={s.code} className={s.code === activeCode ? "active" : ""}>
            <label>
              <input
                type="checkbox"
                checked={selected.has(s.code)}
                onChange={() => toggle(s.code)}
              />
            </label>
            <button type="button" className="watch-stock" onClick={() => onSelect(s.code)}>
              <b>{s.name}</b>
              <span>
                {s.market}.{s.code}
              </span>
            </button>
            <button type="button" className="text-btn danger" onClick={() => void removeCode(s.code)}>
              ×
            </button>
          </li>
        ))}
        {!group?.stocks?.length && <li className="empty">分组为空，研究后点「加入」</li>}
      </ul>
    </aside>
  );
}

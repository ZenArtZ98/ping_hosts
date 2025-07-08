import {useEffect, useState} from "react";
import axios from "axios";

interface Host {
    id: string;
    ip: string;
    last_ping: number | null;
    delivered_pct: number | null;
    lost_pct: number | null;
    last_success: string | null;
}

type SortKey = keyof Host;
type SortDirection = "asc" | "desc";

function validateIp(ip: string): boolean {
    return /^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(\.|$)){4}$/.test(ip);
}

function App() {
    const [hosts, setHosts] = useState<Host[]>([]);
    const [ipInput, setIpInput] = useState<string>("");
    const [editId, setEditId] = useState<string | null>(null);
    const [editIp, setEditIp] = useState<string>("");
    const [sortKey, setSortKey] = useState<SortKey>("ip");
    const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
    const [secondsLeft, setSecondsLeft] = useState<number>(10);
    const [intervalSec, setIntervalSec] = useState<number>(10);

    useEffect(() => {
        const fetchInterval = async () => {
            try {
                const res = await axios.get("/refresh-interval");
                setIntervalSec(res.data.interval);
                setSecondsLeft(res.data.interval);
            } catch (err) {
                console.warn("Couldn't load interval from server, defaulting to 10s");
            }
        };
        fetchInterval();
    }, []);

    useEffect(() => {
        fetchHosts();
        const interval = setInterval(() => {
            fetchHosts();
            setSecondsLeft(intervalSec);
        }, intervalSec * 1000);
        const countdown = setInterval(() => {
            setSecondsLeft((prev) => (prev > 0 ? prev - 1 : 0));
        }, 1000);
        return () => {
            clearInterval(interval);
            clearInterval(countdown);
        };
    }, [intervalSec]);

    const fetchHosts = async () => {
        try {
            const res = await axios.get<Host[]>("/hosts");
            setHosts(res.data);
        } catch (error) {
            console.error("Error fetching hosts:", error);
        }
    };

    const addHost = async () => {
        if (!validateIp(ipInput)) return alert("Invalid IP address");
        const newHost: Host = {
            id: crypto.randomUUID(),
            ip: ipInput,
            last_ping: null,
            delivered_pct: null,
            lost_pct: null,
            last_success: null,
        };
        try {
            await axios.post("/hosts", newHost);
            setIpInput("");
            fetchHosts();
        } catch (err: any) {
            alert(err.response?.data?.detail || "Error adding host");
        }
    };

    const updateHost = async (id: string, ip: string) => {
        if (!validateIp(ip)) return alert("Invalid IP address");
        const updatedHost = hosts.find((h) => h.id === id);
        if (!updatedHost) return;
        const newHost = {...updatedHost, ip};
        try {
            await axios.put(`/hosts/${id}`, newHost);
            setEditId(null);
            setEditIp("");
            fetchHosts();
        } catch (err: any) {
            alert(err.response?.data?.detail || "Error editing host");
        }
    };

    const deleteHost = async (id: string) => {
        await axios.delete(`/hosts/${id}`);
        fetchHosts();
    };

    const exportCsv = async () => {
        const res = await axios.get("/stats/export", {responseType: "blob"});
        const url = window.URL.createObjectURL(new Blob([res.data]));
        const link = document.createElement("a");
        link.href = url;
        link.setAttribute("download", "stats.csv");
        document.body.appendChild(link);
        link.click();
    };

    const importCsv = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;
        const formData = new FormData();
        formData.append("file", file);
        await axios.post("/hosts/import", formData);
        setTimeout(fetchHosts, 1000);
    };

    const sortHosts = (a: Host, b: Host): number => {
        const valA = a[sortKey];
        const valB = b[sortKey];
        if (valA === null) return 1;
        if (valB === null) return -1;
        if (valA === valB) return 0;
        return (valA < valB ? -1 : 1) * (sortDirection === "asc" ? 1 : -1);
    };

    const toggleSort = (key: SortKey) => {
        if (key === sortKey) {
            setSortDirection(sortDirection === "asc" ? "desc" : "asc");
        } else {
            setSortKey(key);
            setSortDirection("asc");
        }
    };

    return (
        <div className="p-4 max-w-4xl mx-auto">
            <h1 className="text-2xl font-bold mb-2">Ping Host</h1>
            <p className="text-gray-600 mb-4">Следующее обновление через: {secondsLeft}с</p>
            <div className="flex items-center gap-2 mb-4">
                <input
                    value={ipInput}
                    onChange={(e) => setIpInput(e.target.value)}
                    className="border p-2 rounded w-full"
                    placeholder="Введит IP-адрес"
                />
                <button onClick={addHost} className="bg-blue-500 text-white px-4 py-2 rounded">
                    Добавить
                </button>
                <input type="file" accept=".csv" onChange={importCsv} className="ml-2"/>
                <button onClick={exportCsv} className="bg-green-600 text-white px-4 py-2 rounded">
                    Экспорт
                </button>
            </div>
            <table className="w-full border">
                <thead>
                <tr className="bg-gray-200">
                    {[
                        ["ip", "Хост"],
                        ["last_ping", "Ping, мс"],
                        ["delivered_pct", "% доставленных пакетов"],
                        ["lost_pct", "% недоставленных пакетов"],
                        ["last_success", "время последнего успешного ping"],
                    ].map(([key, label]) => (
                        <th
                            key={key}
                            className="p-2 border cursor-pointer"
                            onClick={() => toggleSort(key as SortKey)}
                        >
                            {label} {sortKey === key ? (sortDirection === "asc" ? "▲" : "▼") : ""}
                        </th>
                    ))}
                    <th className="p-2 border">Действия</th>
                </tr>
                </thead>
                <tbody>
                {hosts.sort(sortHosts).map((h) => (
                    <tr
                        key={h.id}
                        className={
                            h.delivered_pct != null && h.delivered_pct >= 50
                                ? "bg-green-100"
                                : "bg-red-100"
                        }
                    >
                        <td className="p-2 border">
                            {editId === h.id ? (
                                <input
                                    value={editIp}
                                    onChange={(e) => setEditIp(e.target.value)}
                                    className="border p-1 rounded w-full"
                                />
                            ) : (
                                h.ip
                            )}
                        </td>
                        <td className="p-2 border">{h.last_ping !== null ? h.last_ping.toFixed(0) : "n/a"}</td>
                        <td className="p-2 border">{h.delivered_pct !== null ? `${h.delivered_pct}%` : "n/a"}</td>
                        <td className="p-2 border">{h.lost_pct !== null ? `${h.lost_pct}%` : "n/a"}</td>
                        <td className="p-2 border">{h.last_success || "n/a"}</td>
                        <td className="p-2 border">
                            {editId === h.id ? (
                                <div className="flex gap-1">
                                    <button
                                        onClick={() => updateHost(h.id, editIp)}
                                        className="bg-green-500 text-white px-2 py-1 rounded"
                                    >
                                        Сохранить
                                    </button>
                                    <button
                                        onClick={() => setEditId(null)}
                                        className="bg-gray-400 text-white px-2 py-1 rounded"
                                    >
                                        Отменить
                                    </button>
                                </div>
                            ) : (
                                <div className="flex gap-1">
                                    <button
                                        onClick={() => {
                                            setEditId(h.id);
                                            setEditIp(h.ip);
                                        }}
                                        className="bg-yellow-500 text-white px-2 py-1 rounded"
                                    >
                                        Изменить
                                    </button>
                                    <button
                                        onClick={() => deleteHost(h.id)}
                                        className="bg-red-500 text-white px-2 py-1 rounded"
                                    >
                                        Удалить
                                    </button>
                                </div>
                            )}
                        </td>
                    </tr>
                ))}
                </tbody>
            </table>
        </div>
    );
}

export default App;

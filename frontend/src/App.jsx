import { useState } from "react";
import { useApi } from "./api";
import DecisionView from "./components/DecisionView.jsx";
import AccuracyView from "./components/AccuracyView.jsx";

export default function App() {
  const [tab, setTab] = useState("decision");
  const [cutoff, setCutoff] = useState(9);
  const meta = useApi("/meta", { cutoff_hour: cutoff });

  return (
    <div className="shell">
      <header className="top">
        <div>
          <h1>Wind Desk</h1>
          <p className="sub">GB wind generation: what the day-ahead forecast said, and how far to trust it</p>
        </div>
        <nav className="tabs" aria-label="Views">
          <button className={tab === "decision" ? "on" : ""} onClick={() => setTab("decision")}>
            Decision view
          </button>
          <button className={tab === "accuracy" ? "on" : ""} onClick={() => setTab("accuracy")}>
            Forecast accuracy
          </button>
        </nav>
        <label className="gate">
          Day-ahead gate
          <select value={cutoff} onChange={(e) => setCutoff(Number(e.target.value))}>
            {(meta.data?.cutoff_hours || [6, 7, 8, 9, 10, 11, 12]).map((h) => (
              <option key={h} value={h}>{String(h).padStart(2, "0")}:00 UK, day before</option>
            ))}
          </select>
        </label>
      </header>

      {meta.error && (
        <div className="notice err">
          Could not load data: {meta.error.message}. If you are running locally, check the backend is up and
          that you ran <code>python -m scripts.fetch_data</code>.
        </div>
      )}
      {meta.loading && !meta.data && <div className="notice">Loading…</div>}

      {meta.data && tab === "decision" && <DecisionView meta={meta.data} cutoff={cutoff} />}
      {meta.data && tab === "accuracy" && <AccuracyView meta={meta.data} cutoff={cutoff} />}

      <footer className="foot">
        Data: Elexon BMRS – FUELHH (actual wind) and WINDFOR (wind forecast), national level, decisions made in
        January 2026. Times are UK local time (= UTC in January). Forecast error = forecast − actual.
      </footer>
    </div>
  );
}

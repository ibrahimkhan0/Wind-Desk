import { shortDay } from "../format";

/**
 * Month grid of delivery days. Shade = that day's forecast error (MAE) relative
 * to the worst day, so the desk can see at a glance which days to distrust.
 */
export default function Calendar({ days, selected, onSelect, daily }) {
  const mae = Object.fromEntries((daily || []).map((d) => [d.day, d.mae]));
  const max = Math.max(1, ...Object.values(mae).filter((v) => v != null));
  const first = new Date(days[0] + "T00:00:00Z");
  const lead = (first.getUTCDay() + 6) % 7; // Monday first
  const cells = [...Array(lead).fill(null), ...days];

  return (
    <div className="cal" role="group" aria-label="Delivery day">
      {["M", "T", "W", "T", "F", "S", "S"].map((d, i) => (
        <div key={i} className="cal-h">{d}</div>
      ))}
      {cells.map((d, i) => {
        if (!d) return <div key={`b${i}`} />;
        const v = mae[d];
        const a = v == null ? 0 : 0.12 + 0.7 * (v / max);
        return (
          <button
            key={d}
            className={`cal-d ${d === selected ? "on" : ""}`}
            style={{ "--shade": a }}
            onClick={() => onSelect(d)}
            title={`${shortDay(d)} – average error ${v == null ? "n/a" : Math.round(v).toLocaleString("en-GB") + " MW"}`}
            aria-pressed={d === selected}
          >
            {Number(d.slice(8))}
          </button>
        );
      })}
    </div>
  );
}

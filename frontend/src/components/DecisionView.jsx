import { useState } from "react";
import {
  Area, CartesianGrid, ComposedChart, Legend, Line, LineChart, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { useApi } from "../api";
import { dayLabel, gwh, hhmm, mw, num, when } from "../format";
import Calendar from "./Calendar.jsx";
import Kpi from "./Kpi.jsx";

const C = { actual: "#10242B", forecast: "#0B6E79", band: "#9FD3D8", need: "#B8432F" };

export default function DecisionView({ meta, cutoff }) {
  const days = meta.delivery_days;
  const [day, setDay] = useState(days[Math.min(5, days.length - 1)]);
  const [demand, setDemand] = useState(32000);
  const [showActual, setShowActual] = useState(true);

  const view = useApi("/forecast", { day, cutoff_hour: cutoff });
  const acc = useApi("/accuracy", { cutoff_hour: cutoff });
  const d = view.data;

  const series = d?.series.map((r) => ({
    ...r,
    time: hhmm(r.t),
    bandBase: r.lo,
    bandSpan: r.hi - r.lo,
    need: demand - r.forecast,
    needLo: demand - r.hi,
    needHi: demand - r.lo,
    needSpan: r.hi - r.lo,
  }));

  return (
    <div className="grid">
      <aside className="side">
        <h2>Delivery day</h2>
        <p className="note">Darker day = bigger forecast miss on that day, so you can spot the risky ones.</p>
        <Calendar days={days} selected={day} onSelect={setDay} daily={acc.data?.daily} />
        <div className="legend-cal"><span /> small miss <span className="dark" /> large miss</div>

        <h2>Your demand</h2>
        <label className="field">
          Expected demand, flat (MW)
          <input type="number" min="0" step="500" value={demand} onChange={(e) => setDemand(Number(e.target.value) || 0)} />
        </label>
        <p className="note">
          Demand is not part of this dataset. Enter your own figure to see what is left to buy after wind.
        </p>
      </aside>

      <main>
        {view.error && <div className="notice err">{view.error.message}</div>}
        {d && (
          <>
            <h2 className="day-title">{dayLabel(day)}</h2>
            <p className="lead">
              At the {String(cutoff).padStart(2, "0")}:00 gate on the day before, the latest forecast available
              was issued <strong>{when(d.forecast_issued_max)}</strong>
              {d.forecast_issued_min !== d.forecast_issued_max && ` (earliest period used: ${when(d.forecast_issued_min)})`}.
            </p>

            <div className="kpis">
              <Kpi label="Forecast wind energy" value={gwh(d.summary.forecast_energy_mwh)} hint={`avg ${mw(d.summary.forecast_mean_mw)}`} />
              <Kpi label="Forecast peak / low" value={`${num(d.summary.forecast_peak_mw)} / ${num(d.summary.forecast_min_mw)} MW`} />
              <Kpi
                label="Typical error range"
                value={`${num(-d.band.error_p90_mw)} to ${num(-d.band.error_p10_mw)} MW`}
                hint="actual minus forecast, 80% of periods (Jan 2026)"
              />
              <Kpi
                label="What actually happened"
                value={gwh(d.summary.actual_energy_mwh)}
                hint={`${num((d.summary.forecast_energy_mwh - d.summary.actual_energy_mwh) / 1000, 1)} GWh ${d.summary.forecast_energy_mwh >= d.summary.actual_energy_mwh ? "over" : "under"}-forecast`}
                tone={d.summary.forecast_energy_mwh >= d.summary.actual_energy_mwh ? "warn" : ""}
              />
            </div>

            <section className="card">
              <div className="card-head">
                <h3>Wind generation: forecast you had vs. actual</h3>
                <label className="toggle">
                  <input type="checkbox" checked={showActual} onChange={(e) => setShowActual(e.target.checked)} />
                  Show actual (hindsight)
                </label>
              </div>
              <ResponsiveContainer width="100%" height={320}>
                <ComposedChart data={series} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
                  <CartesianGrid stroke="#D5DEE0" vertical={false} />
                  <XAxis dataKey="time" interval={5} tick={{ fontSize: 12 }} />
                  <YAxis tickFormatter={(v) => `${v / 1000}k`} tick={{ fontSize: 12 }} width={44} unit="" />
                  <Tooltip content={<ChartTip />} />
                  <Area dataKey="bandBase" stackId="b" stroke="none" fill="transparent" legendType="none" isAnimationActive={false} />
                  <Area dataKey="bandSpan" stackId="b" stroke="none" fill={C.band} fillOpacity={0.55} name="Typical error range" isAnimationActive={false} />
                  <Line dataKey="forecast" name="Forecast at decision time" stroke={C.forecast} strokeWidth={2.5} dot={false} isAnimationActive={false} />
                  {showActual && <Line dataKey="actual" name="Actual" stroke={C.actual} strokeWidth={2} strokeDasharray="5 3" dot={false} isAnimationActive={false} />}
                  <Legend verticalAlign="bottom" height={28} />
                </ComposedChart>
              </ResponsiveContainer>
              <p className="axis-note">MW, half-hourly, UK time. The shaded band is the forecast ± the 10th–90th percentile of January error.</p>
            </section>

            <section className="card">
              <h3>What is left to buy after wind (demand {num(demand)} MW)</h3>
              <ResponsiveContainer width="100%" height={260}>
                <ComposedChart data={series} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
                  <CartesianGrid stroke="#D5DEE0" vertical={false} />
                  <XAxis dataKey="time" interval={5} tick={{ fontSize: 12 }} />
                  <YAxis tickFormatter={(v) => `${v / 1000}k`} tick={{ fontSize: 12 }} width={44} />
                  <Tooltip content={<ChartTip />} />
                  <Area dataKey="needLo" stackId="n" stroke="none" fill="transparent" legendType="none" isAnimationActive={false} />
                  <Area dataKey="needSpan" stackId="n" stroke="none" fill={C.need} fillOpacity={0.18} name="Plan for this range" isAnimationActive={false} />
                  <Line dataKey="need" name="Demand − forecast wind" stroke={C.need} strokeWidth={2.5} dot={false} isAnimationActive={false} />
                  <Legend verticalAlign="bottom" height={28} />
                </ComposedChart>
              </ResponsiveContainer>
              <p className="axis-note">
                If wind comes in below forecast you need the top of the band. Planning to the middle line leaves you short
                in roughly {Math.round(acc.data?.metrics.share_over_forecast_pct ?? 50)}% of periods.
              </p>
            </section>

            <section className="card">
              <h3>How the forecast for this day changed as new runs came out</h3>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={d.revisions.map((r) => ({ ...r, label: when(r.publish_time) }))} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
                  <CartesianGrid stroke="#D5DEE0" vertical={false} />
                  <XAxis dataKey="publish_time" tickFormatter={(v) => v.slice(5, 13).replace("T", " ") + "h"} tick={{ fontSize: 11 }} minTickGap={40} />
                  <YAxis tickFormatter={(v) => `${v / 1000}k`} tick={{ fontSize: 12 }} width={44} domain={["auto", "auto"]} />
                  <Tooltip formatter={(v) => `${num(v)} MW`} labelFormatter={(v) => when(v)} />
                  {d.revisions.some((r) => r.before_cutoff) && d.revisions.some((r) => !r.before_cutoff) && (
                    <ReferenceLine x={[...d.revisions].reverse().find((r) => r.before_cutoff)?.publish_time} stroke={C.need} strokeDasharray="4 3" label={{ value: "gate", position: "top", fontSize: 11, fill: C.need }} />
                  )}
                  <Line dataKey="mean_mw" name="Day-average forecast" stroke={C.forecast} strokeWidth={2} dot={{ r: 2 }} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
              <p className="axis-note">Each point is one forecast run. Runs after the gate arrive too late to act on in the day-ahead market.</p>
            </section>
          </>
        )}
      </main>
    </div>
  );
}

function ChartTip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="tip">
      <strong>{label} UK</strong>
      {row.forecast != null && <div>Forecast: {num(row.forecast)} MW</div>}
      {row.actual != null && <div>Actual: {num(row.actual)} MW</div>}
      {row.lo != null && <div>Range: {num(row.lo)} – {num(row.hi)} MW</div>}
      {row.need != null && <div>Left to buy: {num(row.need)} MW</div>}
    </div>
  );
}

import { useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, LineChart, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { useApi } from "../api";
import { num, pct, shortDay } from "../format";
import Kpi from "./Kpi.jsx";

const C = { mae: "#0B6E79", rmse: "#10242B", bias: "#B8432F", under: "#3B6EA8" };

export default function AccuracyView({ meta, cutoff }) {
  const days = meta.delivery_days;
  const [start, setStart] = useState(days[0]);
  const [end, setEnd] = useState(days[days.length - 1]);
  const ok = start <= end;
  const acc = useApi("/accuracy", { start, end, cutoff_hour: cutoff }, ok);
  const hor = useApi("/accuracy/horizon", { start, end }, ok);
  const a = acc.data;
  const m = a?.metrics;

  return (
    <div className="stack">
      <div className="range">
        <label>From
          <select value={start} onChange={(e) => setStart(e.target.value)}>
            {days.map((d) => <option key={d} value={d}>{shortDay(d)}</option>)}
          </select>
        </label>
        <label>To
          <select value={end} onChange={(e) => setEnd(e.target.value)}>
            {days.map((d) => <option key={d} value={d}>{shortDay(d)}</option>)}
          </select>
        </label>
        {!ok && <span className="err-inline">“From” must be on or before “To”.</span>}
        {m && <span className="note">{num(m.n)} half-hours over {m.days} delivery days</span>}
      </div>

      {acc.error && <div className="notice err">{acc.error.message}</div>}

      {m && (
        <>
          <p className="lead">
            Forecasts available at the {String(cutoff).padStart(2, "0")}:00 gate missed actual wind by{" "}
            <strong>{num(m.mae_mw)} MW</strong> on average ({pct(m.wmape_pct)} of generation). They ran{" "}
            <strong>{Math.abs(m.bias_mw) < 50 ? "close to unbiased" : `${num(Math.abs(m.bias_mw))} MW ${m.bias_mw > 0 ? "too high" : "too low"} on average`}</strong>.
            In {pct(m.share_over_forecast_pct, 0)} of periods wind was over-forecast, and one time in ten the
            over-forecast was <strong>{num(m.p90_over_forecast_mw)} MW</strong> or more: a sensible size for a
            safety margin.
          </p>

          <div className="kpis five">
            <Kpi label="MAE" value={`${num(m.mae_mw)} MW`} hint="average miss, either direction" />
            <Kpi label="RMSE" value={`${num(m.rmse_mw)} MW`} hint="punishes big misses more" />
            <Kpi label="Bias" value={`${m.bias_mw > 0 ? "+" : ""}${num(m.bias_mw)} MW`} hint="forecast − actual; + = too high" tone={m.bias_mw > 0 ? "warn" : ""} />
            <Kpi label="wMAPE" value={pct(m.wmape_pct)} hint="total miss ÷ total generation" />
            <Kpi label="Over-forecast, 1 in 10" value={`≥ ${num(m.p90_over_forecast_mw)} MW`} hint="risk of buying too little" tone="warn" />
          </div>

          <div className="two">
            <section className="card">
              <h3>Error by delivery day</h3>
              <ResponsiveContainer width="100%" height={260}>
                <ComposedChart data={a.daily.map((r) => ({ ...r, label: shortDay(r.day) }))} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
                  <CartesianGrid stroke="#D5DEE0" vertical={false} />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} interval="preserveStartEnd" minTickGap={18} />
                  <YAxis tick={{ fontSize: 12 }} width={44} />
                  <Tooltip formatter={(v) => `${num(v)} MW`} />
                  <ReferenceLine y={0} stroke="#10242B" />
                  <Bar dataKey="mae" name="MAE" fill={C.mae} isAnimationActive={false} />
                  <Line dataKey="bias" name="Bias" stroke={C.bias} strokeWidth={2} dot={{ r: 2 }} isAnimationActive={false} />
                  <Legend verticalAlign="bottom" height={28} />
                </ComposedChart>
              </ResponsiveContainer>
            </section>

            <section className="card">
              <h3>Error by time of day</h3>
              <ResponsiveContainer width="100%" height={260}>
                <ComposedChart data={a.by_hour} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
                  <CartesianGrid stroke="#D5DEE0" vertical={false} />
                  <XAxis dataKey="hour" tick={{ fontSize: 12 }} tickFormatter={(h) => `${String(h).padStart(2, "0")}h`} interval={2} />
                  <YAxis tick={{ fontSize: 12 }} width={44} />
                  <Tooltip formatter={(v) => `${num(v)} MW`} labelFormatter={(h) => `${String(h).padStart(2, "0")}:00–${String(h).padStart(2, "0")}:59 UK`} />
                  <ReferenceLine y={0} stroke="#10242B" />
                  <Bar dataKey="mae" name="MAE" fill={C.mae} isAnimationActive={false} />
                  <Line dataKey="bias" name="Bias" stroke={C.bias} strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Legend verticalAlign="bottom" height={28} />
                </ComposedChart>
              </ResponsiveContainer>
            </section>
          </div>

          <div className="two">
            <section className="card">
              <h3>How big is a typical miss?</h3>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={a.histogram.map((b) => ({ ...b, mid: (b.from + b.to) / 2 }))} margin={{ top: 8, right: 8, left: 4, bottom: 0 }} barCategoryGap={1}>
                  <CartesianGrid stroke="#D5DEE0" vertical={false} />
                  <XAxis dataKey="mid" tickFormatter={(v) => `${(v / 1000).toFixed(1)}k`} tick={{ fontSize: 11 }} interval={2} />
                  <YAxis tick={{ fontSize: 12 }} width={40} />
                  <Tooltip formatter={(v) => [v, "half-hours"]} labelFormatter={(v) => `Error around ${num(v)} MW`} />
                  <ReferenceLine x={0} stroke="#10242B" />
                  <Bar dataKey="count" isAnimationActive={false}>
                    {a.histogram.map((b, i) => <Cell key={i} fill={b.to <= 0 ? C.under : C.bias} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <p className="axis-note"><span style={{ color: C.bias }}>Red</span>: wind over-forecast (you under-buy). <span style={{ color: C.under }}>Blue</span>: under-forecast (you over-buy).</p>
            </section>

            <section className="card">
              <h3>Does error grow the earlier you decide?</h3>
              {hor.data && (
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={hor.data.curve} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
                    <CartesianGrid stroke="#D5DEE0" vertical={false} />
                    <XAxis dataKey="horizon_h" tick={{ fontSize: 12 }} label={{ value: "hours ahead of delivery", position: "insideBottom", offset: -2, fontSize: 12 }} height={40} />
                    <YAxis tick={{ fontSize: 12 }} width={44} />
                    <Tooltip formatter={(v) => `${num(v)} MW`} labelFormatter={(h) => `${h} h ahead`} />
                    <ReferenceLine x={Math.round(m.mean_horizon_h)} stroke={C.bias} strokeDasharray="4 3" label={{ value: "avg decision", position: "top", fontSize: 11, fill: C.bias }} />
                    <Line dataKey="mae" name="MAE" stroke={C.mae} strokeWidth={2} dot={false} isAnimationActive={false} />
                    <Line dataKey="rmse" name="RMSE" stroke={C.rmse} strokeWidth={2} dot={false} isAnimationActive={false} />
                    <Legend verticalAlign="bottom" height={28} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </section>
          </div>

          <section className="card">
            <h3>Error by how windy it was</h3>
            <table className="tbl">
              <thead><tr><th>Wind level (quartile of actual)</th><th>MAE</th><th>Bias</th></tr></thead>
              <tbody>
                {a.by_wind_level.map((r) => (
                  <tr key={r.label}><td>{r.label}</td><td>{num(r.mae)} MW</td><td>{r.bias > 0 ? "+" : ""}{num(r.bias)} MW</td></tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  );
}

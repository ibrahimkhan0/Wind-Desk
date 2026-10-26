export const mw = (v, d = 0) =>
  v == null ? "–" : `${Number(v).toLocaleString("en-GB", { maximumFractionDigits: d })} MW`;
export const num = (v, d = 0) =>
  v == null ? "–" : Number(v).toLocaleString("en-GB", { maximumFractionDigits: d });
export const gwh = (mwh) => (mwh == null ? "–" : `${(mwh / 1000).toFixed(1)} GWh`);
export const pct = (v, d = 1) => (v == null ? "–" : `${Number(v).toFixed(d)}%`);

const dtf = new Intl.DateTimeFormat("en-GB", {
  weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC",
});
export const when = (iso) => dtf.format(new Date(iso)).replace(",", "") + " UK";
export const hhmm = (iso) => iso.slice(11, 16);
export const dayLabel = (d) =>
  new Date(d + "T00:00:00Z").toLocaleDateString("en-GB", {
    weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC",
  });
export const shortDay = (d) =>
  new Date(d + "T00:00:00Z").toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });

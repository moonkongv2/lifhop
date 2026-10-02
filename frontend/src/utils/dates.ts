export function validDate(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith("0000")) return false;
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
}
export function validLocalDateTime(value: string) {
  const [date, time] = value.split("T");
  if (!validDate(date) || !/^([01]\d|2[0-3]):[0-5]\d$/.test(time ?? "")) return false;
  const parsed = new Date(value);
  return parsed.getFullYear() === Number(date.slice(0, 4)) && parsed.getMonth() + 1 === Number(date.slice(5, 7))
    && parsed.getDate() === Number(date.slice(8, 10)) && parsed.getHours() === Number(time.slice(0, 2))
    && parsed.getMinutes() === Number(time.slice(3, 5));
}

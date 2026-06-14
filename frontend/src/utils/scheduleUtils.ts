export type SchedulePreset =
  | "twice_daily"
  | "daily"
  | "every_2_days"
  | "every_3_days"
  | "weekly"
  | "custom";

export type CustomMode = "interval" | "cron";
export type IntervalUnit = "hours" | "days";

export interface ScheduleState {
  preset: SchedulePreset;
  time: string;          // HH:MM 24-hour
  dayOfWeek: number;     // 0=Sun ... 6=Sat
  timezone: string;      // IANA key
  customMode: CustomMode;
  intervalValue: number;
  intervalUnit: IntervalUnit;
  cronExpression: string; // raw cron, used when preset=custom and customMode=cron
}

export const TIMEZONES: { label: string; iana: string }[] = [
  { label: "IST (UTC+5:30)", iana: "Asia/Kolkata" },
  { label: "UTC", iana: "UTC" },
  { label: "GMT (UTC+0)", iana: "Europe/London" },
  { label: "EST (UTC-5)", iana: "America/New_York" },
  { label: "CST (UTC-6)", iana: "America/Chicago" },
  { label: "PST (UTC-8)", iana: "America/Los_Angeles" },
  { label: "CET (UTC+1)", iana: "Europe/Berlin" },
  { label: "SGT (UTC+8)", iana: "Asia/Singapore" },
  { label: "JST (UTC+9)", iana: "Asia/Tokyo" },
  { label: "AEST (UTC+10)", iana: "Australia/Sydney" },
];

export const PRESETS: { value: SchedulePreset; label: string }[] = [
  { value: "twice_daily", label: "Twice daily" },
  { value: "daily", label: "Daily" },
  { value: "every_2_days", label: "Every 2 days" },
  { value: "every_3_days", label: "Every 3 days" },
  { value: "weekly", label: "Weekly" },
  { value: "custom", label: "Custom" },
];

export const DAY_LABELS = ["S", "M", "T", "W", "T", "F", "S"];
const DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

function parseTime(time: string): { hour: number; min: number } {
  const [h, m] = time.split(":").map(Number);
  return { hour: h, min: m };
}

export function presetToCron(state: ScheduleState): string {
  const { hour, min } = parseTime(state.time);

  switch (state.preset) {
    case "twice_daily": {
      const hour2 = (hour + 12) % 24;
      return `${min} ${hour},${hour2} * * *`;
    }
    case "daily":
      return `${min} ${hour} * * *`;
    case "every_2_days":
      return `${min} ${hour} */2 * *`;
    case "every_3_days":
      return `${min} ${hour} */3 * *`;
    case "weekly":
      return `${min} ${hour} * * ${state.dayOfWeek}`;
    case "custom":
      if (state.customMode === "cron") return state.cronExpression;
      if (state.intervalUnit === "hours") return `0 */${state.intervalValue} * * *`;
      return `${min} ${hour} */${state.intervalValue} * *`;
  }
}

export function describeSchedule(state: ScheduleState): string {
  const tzLabel = TIMEZONES.find((t) => t.iana === state.timezone)?.label ?? state.timezone;
  const { hour, min } = parseTime(state.time);
  const minPad = String(min).padStart(2, "0");

  switch (state.preset) {
    case "twice_daily": {
      const hour2 = (hour + 12) % 24;
      const h2Pad = String(hour2).padStart(2, "0");
      return `Runs twice per day at ${state.time} and ${h2Pad}:${minPad} ${tzLabel}.`;
    }
    case "daily":
      return `Runs once per day at ${state.time} ${tzLabel}.`;
    case "every_2_days":
      return `Runs every 2 days at ${state.time} ${tzLabel}.`;
    case "every_3_days":
      return `Runs every 3 days at ${state.time} ${tzLabel}.`;
    case "weekly":
      return `Runs every ${DAY_NAMES[state.dayOfWeek]} at ${state.time} ${tzLabel}.`;
    case "custom":
      if (state.customMode === "cron") return `Custom schedule: ${state.cronExpression}`;
      if (state.intervalUnit === "hours") return `Runs every ${state.intervalValue} hour(s).`;
      return `Runs every ${state.intervalValue} day(s) at ${state.time} ${tzLabel}.`;
  }
}

export function stateFromSettings(s: Record<string, unknown>): ScheduleState {
  return {
    preset: (s.schedule_preset as SchedulePreset) ?? "custom",
    time: (s.schedule_time as string) ?? "06:00",
    dayOfWeek: (s.schedule_day_of_week as number) ?? 1,
    timezone: (s.schedule_timezone as string) ?? "Asia/Kolkata",
    customMode: (s.schedule_custom_mode as CustomMode) ?? "cron",
    intervalValue: (s.schedule_interval_value as number) ?? 4,
    intervalUnit: (s.schedule_interval_unit as IntervalUnit) ?? "hours",
    cronExpression: (s.schedule_cron as string) ?? "0 */4 * * *",
  };
}

export function stateToSettingsPayload(state: ScheduleState): Record<string, unknown> {
  return {
    schedule_preset: state.preset,
    schedule_time: state.time,
    schedule_day_of_week: state.dayOfWeek,
    schedule_timezone: state.timezone,
    schedule_custom_mode: state.customMode,
    schedule_interval_value: state.intervalValue,
    schedule_interval_unit: state.intervalUnit,
    schedule_cron: presetToCron(state),
  };
}

import { describe, it, expect } from "vitest";
import { presetToCron, describeSchedule, type ScheduleState } from "./scheduleUtils";

const base: ScheduleState = {
  preset: "daily",
  time: "09:00",
  dayOfWeek: 1,
  timezone: "Asia/Kolkata",
  customMode: "interval",
  intervalValue: 4,
  intervalUnit: "hours",
  cronExpression: "0 */4 * * *",
};

describe("presetToCron", () => {
  it("daily at 09:00 → 0 9 * * *", () => {
    expect(presetToCron({ ...base, preset: "daily", time: "09:00" })).toBe("0 9 * * *");
  });

  it("daily at 09:30 → 30 9 * * *", () => {
    expect(presetToCron({ ...base, preset: "daily", time: "09:30" })).toBe("30 9 * * *");
  });

  it("twice_daily at 09:00 → 0 9,21 * * *", () => {
    expect(presetToCron({ ...base, preset: "twice_daily", time: "09:00" })).toBe("0 9,21 * * *");
  });

  it("twice_daily at 22:00 wraps correctly → 0 22,10 * * *", () => {
    expect(presetToCron({ ...base, preset: "twice_daily", time: "22:00" })).toBe("0 22,10 * * *");
  });

  it("every_2_days at 09:00 → 0 9 */2 * *", () => {
    expect(presetToCron({ ...base, preset: "every_2_days", time: "09:00" })).toBe("0 9 */2 * *");
  });

  it("every_3_days at 09:00 → 0 9 */3 * *", () => {
    expect(presetToCron({ ...base, preset: "every_3_days", time: "09:00" })).toBe("0 9 */3 * *");
  });

  it("weekly on Monday (1) at 09:00 → 0 9 * * 1", () => {
    expect(presetToCron({ ...base, preset: "weekly", time: "09:00", dayOfWeek: 1 })).toBe("0 9 * * 1");
  });

  it("weekly on Sunday (0) at 00:00 → 0 0 * * 0", () => {
    expect(presetToCron({ ...base, preset: "weekly", time: "00:00", dayOfWeek: 0 })).toBe("0 0 * * 0");
  });

  it("custom interval hours → 0 */4 * * *", () => {
    expect(presetToCron({ ...base, preset: "custom", customMode: "interval", intervalValue: 4, intervalUnit: "hours" })).toBe("0 */4 * * *");
  });

  it("custom interval days at 09:00 → 0 9 */3 * *", () => {
    expect(presetToCron({ ...base, preset: "custom", customMode: "interval", intervalValue: 3, intervalUnit: "days", time: "09:00" })).toBe("0 9 */3 * *");
  });

  it("custom cron → returned as-is", () => {
    expect(presetToCron({ ...base, preset: "custom", customMode: "cron", cronExpression: "*/15 * * * *" })).toBe("*/15 * * * *");
  });
});

describe("describeSchedule", () => {
  it("daily description mentions time and timezone label", () => {
    const result = describeSchedule({ ...base, preset: "daily", time: "09:00", timezone: "Asia/Kolkata" });
    expect(result).toContain("09:00");
    expect(result).toContain("IST");
  });

  it("weekly description mentions day name", () => {
    const result = describeSchedule({ ...base, preset: "weekly", dayOfWeek: 1 });
    expect(result).toContain("Monday");
  });

  it("twice daily shows both hours", () => {
    const result = describeSchedule({ ...base, preset: "twice_daily", time: "09:00" });
    expect(result).toContain("09:00");
    expect(result).toContain("21:00");
  });

  it("custom interval hours shows count", () => {
    const result = describeSchedule({ ...base, preset: "custom", customMode: "interval", intervalValue: 4, intervalUnit: "hours" });
    expect(result).toContain("4");
    expect(result).toContain("hour");
  });
});

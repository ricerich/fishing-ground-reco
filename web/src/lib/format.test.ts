import { describe, expect, it } from "vitest";
import { addDays, dayLabel, fillNote, pct, weight } from "./format";

describe("format", () => {
  it("요일은 문자열에서 바로 (시간대 영향 없음)", () => {
    expect(dayLabel("2026-10-15")).toBe("10월 15일(목)");
    expect(addDays("2026-10-31", 1)).toBe("2026-11-01");
  });
  it("무게 · 비율", () => {
    expect(weight(756)).toBe("756kg");
    expect(weight(1720)).toBe("1.7톤");
    expect(weight(17339)).toBe("17톤");
    expect(pct(0.6417)).toBe("64%");
    expect(pct(null)).toBe("—");
  });
  it("어제 위판이 덜 들어오면 알린다", () => {
    expect(fillNote(0.083).low).toBe(true);
    expect(fillNote(2.05).low).toBe(false);
  });
});

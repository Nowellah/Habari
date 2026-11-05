import { describe, expect, it } from "vitest";
import { AGES, ageLabel, languageName, spokenLanguageFor } from "./choices";

describe("choices", () => {
  it("shows an age label only when an age was chosen", () => {
    expect(ageLabel("10_12")).toBe("10–12");
    expect(ageLabel("none")).toBeNull();
    expect(ageLabel(null)).toBeNull();
  });
  it("age values are safe to send as server flags", () => {
    for (const a of AGES) expect(a.value).toMatch(/^[a-z0-9_]+$/);
  });
  it("names languages and picks a spoken language", () => {
    expect(languageName("lg")).toBe("Luganda");
    expect(spokenLanguageFor("lg")).toBe("lg");
    expect(spokenLanguageFor("sw")).toBe("en");
  });
});

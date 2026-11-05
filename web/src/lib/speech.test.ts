import { describe, expect, it } from "vitest";
import { matchOption, plain, speechText } from "./speech";

const options = [{ key: "2", label: "A lot" }, { key: "3", label: "Scared" }];

describe("matchOption", () => {
  it("matches the words on a button, ignoring case and punctuation", () => {
    expect(matchOption("a lot.", options)?.key).toBe("2");
    expect(matchOption("  SCARED ", options)?.key).toBe("3");
  });
  it("does not match other text or empty text", () => {
    expect(matchOption("a lot of things happened", options)).toBeNull();
    expect(matchOption("", options)).toBeNull();
  });
});

describe("speechText", () => {
  it("speaks long numbers digit by digit", () => {
    expect(speechText("Call 116 now, it is free.", [])).toBe("Call 1 1 6 now, it is free.");
  });
  it("replaces a typed list with the question and the button labels", () => {
    const text = "How does this feel for you? 1 A little 2 A lot. Reply 0 to skip.";
    const out = speechText(text, [{ key: "1", label: "A little" }, { key: "2", label: "A lot" }]);
    expect(out).toBe("How does this feel for you? You can choose: A little, A lot.");
  });
  it("turns line breaks into pauses", () => {
    expect(speechText("One\nTwo", [])).toBe("One. Two");
  });
});

describe("plain", () => {
  it("keeps letters, digits and spaces", () => {
    expect(plain("Asked for pics/money!")).toBe("asked for picsmoney");
  });
});

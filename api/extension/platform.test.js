// Run with: node --test extension/
const test = require("node:test");
const assert = require("node:assert");
const { detectPlatform } = require("./platform.js");

test("known social platforms are recognised", () => {
  assert.equal(detectPlatform("https://www.instagram.com/p/abc"), "instagram");
  assert.equal(detectPlatform("https://www.tiktok.com/@someone/video/1"), "tiktok");
  assert.equal(detectPlatform("https://web.snapchat.com/"), "snapchat");
  assert.equal(detectPlatform("https://www.linkedin.com/in/x"), "linkedin");
  assert.equal(detectPlatform("https://www.facebook.com/x"), "facebook");
  assert.equal(detectPlatform("https://discord.com/channels/1"), "discord");
  assert.equal(detectPlatform("https://www.roblox.com/games/1"), "roblox");
  assert.equal(detectPlatform("https://www.youtube.com/watch?v=1"), "youtube");
});

test("x.com and twitter.com are both X", () => {
  assert.equal(detectPlatform("https://x.com/someone"), "x");
  assert.equal(detectPlatform("https://twitter.com/someone"), "x");
});

test("WhatsApp Web is recognised", () => {
  assert.equal(detectPlatform("https://web.whatsapp.com/"), "whatsapp");
});

test("look-alike domains are not trusted", () => {
  assert.equal(detectPlatform("https://instagram.com.evil.example/p"), "web");
  assert.equal(detectPlatform("https://notinstagram.com/"), "web");
});

test("unknown or broken links fall back to web", () => {
  assert.equal(detectPlatform("https://example.org/"), "web");
  assert.equal(detectPlatform("not a url"), "web");
  assert.equal(detectPlatform(""), "web");
});

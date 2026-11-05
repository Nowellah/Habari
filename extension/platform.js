// Which platform is this page on? Exact domain or a subdomain of it only,
// so "instagram.com.evil.example" is not mistaken for Instagram.
const PLATFORMS = {
  "instagram.com": "instagram",
  "tiktok.com": "tiktok",
  "snapchat.com": "snapchat",
  "x.com": "x",
  "twitter.com": "x",
  "linkedin.com": "linkedin",
  "facebook.com": "facebook",
  "web.whatsapp.com": "whatsapp",
  "discord.com": "discord",
  "roblox.com": "roblox",
  "youtube.com": "youtube",
};

function detectPlatform(url) {
  let host;
  try {
    host = new URL(url).hostname.toLowerCase();
  } catch (e) {
    return "web";
  }
  for (const [domain, name] of Object.entries(PLATFORMS)) {
    if (host === domain || host.endsWith("." + domain)) return name;
  }
  return "web";
}

if (typeof module !== "undefined") module.exports = { detectPlatform };

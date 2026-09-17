// Public backend address only. Never put API keys in this file.
window.MATRACARE_CONFIG = {
  apiBaseUrl: ["localhost", "127.0.0.1"].includes(window.location.hostname)
    ? ""
    : "https://maternity-taupe.vercel.app"
};

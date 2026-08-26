#!/usr/bin/env node

import { spawn } from "node:child_process";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const [chromium, pageUrl] = process.argv.slice(2);
if (!chromium || !pageUrl) {
  console.error("usage: mw_slide_browser_probe.mjs <chromium> <file-url>");
  process.exit(2);
}

const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
const deadline = Date.now() + 30000;
const withTimeout = (promise, label, milliseconds = 3000) => Promise.race([
  promise,
  new Promise((_, reject) => setTimeout(() => reject(new Error(`${label} timed out`)), milliseconds)),
]);
const profile = `${dirname(fileURLToPath(pageUrl))}/chromium-profile`;
const browser = spawn(
  chromium,
  [
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    "--allow-file-access-from-files",
    "--hide-scrollbars",
    "--window-size=1280,720",
    "--remote-debugging-port=0",
    `--user-data-dir=${profile}`,
    "about:blank",
  ],
  { stdio: ["ignore", "ignore", "pipe"] },
);

let browserStderr = "";
browser.stderr.setEncoding("utf8");
browser.stderr.on("data", (chunk) => {
  browserStderr = (browserStderr + chunk).slice(-4000);
});

const cleanup = () => {
  browser.stderr.destroy();
  if (browser.exitCode === null) browser.kill("SIGKILL");
  browser.unref();
};
process.on("exit", cleanup);
process.on("SIGINT", () => process.exit(130));
process.on("SIGTERM", () => process.exit(143));

async function devtoolsEndpoint() {
  while (Date.now() < deadline) {
    const match = browserStderr.match(/DevTools listening on (ws:\/\/[^\s]+)/);
    if (match) return match[1];
    if (browser.exitCode !== null) throw new Error(`Chromium exited ${browser.exitCode}`);
    await delay(50);
  }
  throw new Error("Chromium did not expose a DevTools endpoint");
}

function connectCdp(webSocketUrl) {
  const socket = new WebSocket(webSocketUrl);
  let nextId = 1;
  const pending = new Map();
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(String(event.data));
    if (!message.id || !pending.has(message.id)) return;
    const { resolve, reject } = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) reject(new Error(message.error.message));
    else resolve(message.result || {});
  });
  const opened = new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", () => reject(new Error("DevTools WebSocket failed")), { once: true });
  });
  return {
    opened,
    close: () => socket.close(),
    send: async (method, params = {}) => {
      await withTimeout(opened, "DevTools WebSocket connection");
      const id = nextId++;
      const response = new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
      socket.send(JSON.stringify({ id, method, params }));
      const timeout = method === "Runtime.evaluate" ? 20000 : 3000;
      return withTimeout(response, `DevTools ${method}`, timeout);
    },
  };
}

let browserCdp = null;
try {
  const endpoint = await devtoolsEndpoint();
  browserCdp = connectCdp(endpoint);
  await withTimeout(browserCdp.opened, "Browser DevTools WebSocket connection");
  const endpointUrl = new URL(endpoint);
  const targetResponse = await withTimeout(fetch(
    `http://${endpointUrl.host}/json/new?${encodeURIComponent(pageUrl)}`,
    { method: "PUT" },
  ), "DevTools target creation");
  if (!targetResponse.ok) throw new Error(`Could not create browser target: ${targetResponse.status}`);
  const target = await targetResponse.json();
  const cdp = connectCdp(target.webSocketDebuggerUrl);
  await withTimeout(cdp.opened, "DevTools WebSocket connection");
  await cdp.send("Runtime.enable");

  let result = null;
  while (Date.now() < deadline) {
    const evaluated = await cdp.send("Runtime.evaluate", {
      expression: "document.getElementById('mary-image-overflow-audit-result')?.textContent || null",
      returnByValue: true,
    });
    result = evaluated.result?.value ?? null;
    if (result) break;
    await delay(100);
  }
  cdp.close();
  if (!result) throw new Error("Browser page produced no image overflow result");
  JSON.parse(result);
  process.stdout.write(result);
} catch (error) {
  const detail = browserStderr.trim().split("\n").slice(-2).join(" ");
  console.error(`${error instanceof Error ? error.message : String(error)}${detail ? `; ${detail}` : ""}`);
  process.exitCode = 1;
} finally {
  if (browserCdp) {
    try {
      await browserCdp.send("Browser.close");
      browserCdp.close();
      await delay(300);
    } catch {
      // The process cleanup below remains the fallback.
    }
  }
  cleanup();
}
process.exit(process.exitCode || 0);

#!/usr/bin/env node

import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [baseUrl, messageKey, screenshotPath] = process.argv.slice(2);
if (!baseUrl || !messageKey) throw new Error("usage: browser-proof BASE_URL MESSAGE_KEY [SCREENSHOT]");

const candidates = [
  process.env.RFI_CHROME_BINARY,
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
].filter(Boolean);
const chromeBinary = candidates.find(existsSync);
if (!chromeBinary) throw new Error("Chrome or Chromium is required for the message-viewer UI proof");

const profile = mkdtempSync(join(tmpdir(), "rfi-message-viewer-chrome-"));
const chrome = spawn(chromeBinary, [
  "--headless=new",
  "--disable-background-networking",
  "--disable-component-update",
  "--disable-default-apps",
  "--disable-dev-shm-usage",
  "--disable-extensions",
  "--disable-gpu",
  "--no-first-run",
  "--no-sandbox",
  "--remote-debugging-port=0",
  `--user-data-dir=${profile}`,
  "about:blank",
], { stdio: "ignore" });

const pause = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
let client;
try {
  const portFile = join(profile, "DevToolsActivePort");
  for (let attempt = 0; attempt < 100 && !existsSync(portFile); attempt += 1) await pause(50);
  if (!existsSync(portFile)) throw new Error("Chrome did not expose its debugging endpoint");
  const port = readFileSync(portFile, "utf8").split(/\r?\n/)[0];
  const targetResponse = await fetch(
    `http://127.0.0.1:${port}/json/new?${encodeURIComponent(baseUrl + "/artifacts")}`,
    { method: "PUT" },
  );
  if (!targetResponse.ok) throw new Error(`cannot create browser target: ${targetResponse.status}`);
  const target = await targetResponse.json();
  const socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.onopen = resolve;
    socket.onerror = () => reject(new Error("cannot connect to Chrome DevTools"));
  });

  let sequence = 0;
  const pending = new Map();
  const listeners = new Map();
  socket.onmessage = async event => {
    const payload = typeof event.data === "string" ? event.data : await event.data.text();
    const message = JSON.parse(payload);
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message));
      else resolve(message.result);
    } else if (message.method && listeners.has(message.method)) {
      listeners.get(message.method).splice(0).forEach(resolve => resolve(message.params));
    }
  };
  client = {
    send(method, params = {}) {
      const id = ++sequence;
      socket.send(JSON.stringify({ id, method, params }));
      return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
    },
    event(method) {
      return new Promise(resolve => {
        if (!listeners.has(method)) listeners.set(method, []);
        listeners.get(method).push(resolve);
      });
    },
    close() { socket.close(); },
  };

  const evaluate = async expression => {
    const result = await client.send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
    return result.result.value;
  };
  const viewport = (width, height) => client.send("Emulation.setDeviceMetricsOverride", {
    width, height, deviceScaleFactor: 1, mobile: false,
  });
  const geometry = () => evaluate(`(() => {
    const body=document.querySelector('.message-body'), preview=document.querySelector('#preview');
    const b=body.getBoundingClientRect(), p=preview.getBoundingClientRect();
    return {clientHeight:body.clientHeight,scrollHeight:body.scrollHeight,overflowY:getComputedStyle(body).overflowY,
      bodyTop:b.top,bodyBottom:b.bottom,previewTop:p.top,previewBottom:p.bottom,
      visible:b.height>0&&b.bottom>0&&b.top<innerHeight,viewportWidth:innerWidth,viewportHeight:innerHeight};
  })()`);

  await client.send("Page.enable");
  await client.send("Runtime.enable");
  await viewport(1440, 900);
  const loaded = client.event("Page.loadEventFired");
  await client.send("Page.navigate", { url: baseUrl + "/artifacts" });
  await loaded;
  const initial = await evaluate(`(async()=>{
    const detail=await fetch('/api/mailing-lists/messages/${encodeURIComponent(messageKey)}').then(r=>r.json());
    document.querySelector('#empty').classList.add('hidden');
    document.querySelector('#artifact-view').classList.remove('hidden');
    await renderMailDetail(detail);
    document.querySelector('#metadata').classList.add('hidden');
    document.querySelector('#metadata-toggle').setAttribute('aria-expanded','false');
    const raw=await fetch('/api/mailing-lists/messages/${encodeURIComponent(messageKey)}/content').then(r=>r.text());
    const headers=document.querySelector('.message-headers-content');
    const body=document.querySelector('.message-body');
    return {headerCollapsed:headers.classList.contains('hidden'),headerContainsLast:headers.textContent.includes('X-Long-Header-220:'),
      bodyContainsStart:body.textContent.includes('BODY-LINE-000'),bodyContainsEnd:body.textContent.includes('BODY-END-MARKER'),
      sectionsDistinct:headers.parentElement!==body&&headers.textContent.indexOf('BODY-LINE-000')===-1,
      rawBytes:new TextEncoder().encode(raw).length,bodyTabIndex:body.tabIndex,bodyRole:body.getAttribute('role')};
  })()`);
  const desktop = await geometry();
  if (screenshotPath) {
    const image = await client.send("Page.captureScreenshot", { format: "png", fromSurface: true });
    const initialPath = screenshotPath.endsWith(".png")
      ? screenshotPath.slice(0, -4) + "-initial.png"
      : screenshotPath + "-initial.png";
    writeFileSync(initialPath, Buffer.from(image.data, "base64"));
  }
  const point = await evaluate(`(()=>{const r=document.querySelector('.message-body').getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}})()`);
  await client.send("Input.dispatchMouseEvent", {
    type: "mouseWheel", x: point.x, y: point.y, deltaX: 0, deltaY: 520,
  });
  await pause(100);
  const wheelScrollTop = await evaluate("document.querySelector('.message-body').scrollTop");
  await evaluate("document.querySelector('.message-body').focus()");
  await client.send("Input.dispatchKeyEvent", {
    type: "keyDown", key: "PageDown", code: "PageDown", windowsVirtualKeyCode: 34,
  });
  await client.send("Input.dispatchKeyEvent", {
    type: "keyUp", key: "PageDown", code: "PageDown", windowsVirtualKeyCode: 34,
  });
  await pause(100);
  const keyboardScrollTop = await evaluate("document.querySelector('.message-body').scrollTop");
  await viewport(700, 800);
  await pause(100);
  await evaluate("document.querySelector('.detail-pane').scrollIntoView({block:'start'})");
  await pause(100);
  const mobile = await geometry();
  await viewport(1440, 900);
  await pause(100);
  if (screenshotPath) {
    const image = await client.send("Page.captureScreenshot", { format: "png", fromSurface: true });
    writeFileSync(screenshotPath, Buffer.from(image.data, "base64"));
  }
  console.log(JSON.stringify({ initial, desktop, mobile, wheelScrollTop, keyboardScrollTop }, null, 2));
} finally {
  if (client) client.close();
  chrome.kill("SIGTERM");
  await pause(100);
  rmSync(profile, { recursive: true, force: true });
}

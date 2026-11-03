// Capture UI screenshots of the local demo instance with headless Chrome (DevTools Protocol, no npm packages).
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";

const BASE = "http://127.0.0.1:8011";
const OUT = process.env.OUT || new URL("./png/", import.meta.url).pathname;
const PW = "demo-pass-12345";
const [, , visitId, ticket, portalId] = process.argv;
mkdirSync(OUT, { recursive: true });

const chrome = spawn("google-chrome", [
    "--headless=new", "--remote-debugging-port=9333", "--no-first-run", "--no-default-browser-check",
    `--user-data-dir=${process.env.PROFILE || "/tmp/hyplus-preview-profile"}`, "--hide-scrollbars", "--force-color-profile=srgb",
    "--disable-features=Translate", "about:blank",
], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
process.on("exit", () => chrome.kill());
process.on("uncaughtException", (e) => { console.error(e.message); chrome.kill(); process.exit(1); });

let ws, id = 0;
const pending = new Map(), listeners = [];
async function connect() {
    for (let i = 0; i < 50; i++) {
        try { const v = await (await fetch("http://127.0.0.1:9333/json/version")).json(); ws = new WebSocket(v.webSocketDebuggerUrl); break; }
        catch { await sleep(200); }
    }
    await new Promise((r) => (ws.onopen = r));
    ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        if (msg.id && pending.has(msg.id)) { const { resolve, reject } = pending.get(msg.id); pending.delete(msg.id); msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result); }
        else listeners.forEach((fn) => fn(msg));
    };
}
function send(method, params = {}, sessionId) {
    return new Promise((resolve, reject) => { const mid = ++id; pending.set(mid, { resolve, reject }); ws.send(JSON.stringify({ id: mid, method, params, sessionId })); });
}

let session;
async function newPage() {
    const { targetId } = await send("Target.createTarget", { url: "about:blank" });
    session = (await send("Target.attachToTarget", { targetId, flatten: true })).sessionId;
    await send("Page.enable", {}, session);
    await send("Runtime.enable", {}, session);
}
const js = async (expression) => {
    const r = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true }, session);
    if (r.exceptionDetails) {
        const where = await send("Runtime.evaluate", { expression: "location.href + ' | ' + document.title", returnByValue: true }, session);
        throw new Error((r.exceptionDetails.exception?.description || r.exceptionDetails.text) + " @ " + where.result.value + " :: " + expression.slice(0, 80));
    }
    return r.result.value;
};
function loaded() {
    return new Promise((resolve) => {
        const fn = (msg) => { if (msg.method === "Page.loadEventFired" && msg.sessionId === session) { listeners.splice(listeners.indexOf(fn), 1); resolve(); } };
        listeners.push(fn);
    });
}
async function go(path) { const done = loaded(); await send("Page.navigate", { url: BASE + path }, session); await done; await sleep(600); }
async function viewport(width, height, scale = 1, mobile = false) {
    await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: scale, mobile }, session);
}
const STILL = `{const s=document.createElement('style');s.textContent='*{animation:none!important;transition:none!important;caret-color:transparent!important} .js-motion [data-reveal]{opacity:1!important;transform:none!important}';document.head.appendChild(s);}`;
async function shot(name, fullHeight) {
    await js(STILL);
    await sleep(400);
    const params = { format: "png" };
    if (fullHeight) {
        const h = await js("document.documentElement.scrollHeight");
        const w = await js("document.documentElement.clientWidth");
        params.clip = { x: 0, y: 0, width: w, height: Math.min(h, fullHeight), scale: 1 };
        params.captureBeyondViewport = true;
    }
    const { data } = await send("Page.captureScreenshot", params, session);
    writeFileSync(OUT + name + ".png", Buffer.from(data, "base64"));
    console.log("saved", name);
}
// A whole page, or one element of it: grow the viewport to fit so lazy images and charts render for real.
async function tall(name, selector) {
    const width = await js("document.documentElement.clientWidth");
    await viewport(width, await js("document.documentElement.scrollHeight"), 1.5);
    await js(STILL);
    await sleep(1800);
    const params = { format: "png" };
    if (selector) {
        const r = JSON.parse(await js(`(()=>{const r=document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();return JSON.stringify({x:r.left+scrollX,y:r.top+scrollY,width:r.width,height:r.height})})()`));
        params.clip = { ...r, scale: 1 };
    }
    const { data } = await send("Page.captureScreenshot", params, session);
    writeFileSync(OUT + name + ".png", Buffer.from(data, "base64"));
    console.log("saved", name);
    await viewport(width, 900, 1.5);
}
async function login(user) {
    await go("/accounts/login/");
    const done = loaded();
    await js(`document.querySelector('[name=username]').value=${JSON.stringify(user)};document.querySelector('[name=password]').value=${JSON.stringify(PW)};document.querySelector('form').submit()`);
    await done; await sleep(500);
}
async function logout() {
    await js(`fetch('/accounts/logout/',{method:'POST',headers:{'X-CSRFToken':getCsrfToken()}})`); await sleep(300);
}

await connect();
await newPage();

// 0. The public platform page.
await viewport(1440, 900, 1.5);
await go("/"); await sleep(800); await shot("platform");
await tall("platform-benefits", "#benefits");
await tall("platform-integrations", "#devices");
await tall("platform-brands", "#brands");

// 1. Kiosk: register this browser as a kiosk (nurse), sign out, then walk through check-in.
await viewport(1440, 900, 1.5);
await login("nurse");
await go("/devices/");
await js(`fetch('/devices/kiosks/register/',{method:'POST',headers:{'X-CSRFToken':getCsrfToken(),'Content-Type':'application/x-www-form-urlencoded'},body:'name=Lobby+kiosk'})`);
await sleep(500);
await logout();
await go("/kiosk/");
await js("Voice.recognition=null; Voice.say=()=>{}; DeviceReader.start=()=>{};");
await shot("kiosk-welcome");
await js(`begin('new'); document.getElementById('input-name').value='Maya Putri'; document.getElementById('input-reason').value='Routine blood pressure check'; updateContinue();`);
await js(`startVisit(new Event('submit'))`); await sleep(1200);
await shot("kiosk-doctor");
await js(`pickDoctor(state.doctors[0].id)`); await sleep(1500);
await js(`simulate('weight')`); await sleep(1000);
await js(`go(3)`); await sleep(500);
await js(`simulate('bp')`); await sleep(1000);
await shot("kiosk-bp");
await js(`go(4)`); await sleep(2000);
await shot("kiosk-ticket");

// 2. Waiting-room TV (public).
await viewport(1920, 1080, 1);
await go("/display/");
await js(`document.getElementById('start')?.remove()`); await sleep(3500);
await shot("tv");

// 3-5. Doctor screens.
await viewport(1440, 900, 1.5);
await login("budi");
await go("/doctor/"); await shot("doctor-queue");
await go(`/visits/${visitId}/`); await sleep(800); await shot("doctor-visit", 1250);
await logout();

// 6. Clinic dashboard (administrator).
// The demo has no Bluetooth gateway: report the two integrated OMRON devices, as a live clinic would.
await fetch(BASE + "/internal/gateway/heartbeat/", { method: "POST", headers: { Authorization: "Bearer " + process.env.GATEWAY_TOKEN, "Content-Type": "application/json" },
    body: JSON.stringify({ devices: [{ kind: "bp", model: "HEM-6232T", address: "AA:BB:CC:00:00:01" }, { kind: "weight", model: "HN-300T2", address: "AA:BB:CC:00:00:02" }] }) });
await login("admin");
await go("/dashboard/"); await sleep(1800); await tall("dashboard");
await go("/analytics/?days=30"); await tall("analytics");
await go("/settings/"); await tall("settings");
await go("/schedules/"); await shot("schedules");
await logout();

// 7-8. Patient phone: ticket with live queue position, and the patient portal.
await viewport(390, 844, 2, true);
await go(`/v/${ticket}/`); await sleep(1500); await shot("phone-ticket");
await go("/portal/login/");
{
    const done = loaded();
    await js(`document.querySelector('[name=username]').value=${JSON.stringify(portalId)};document.querySelector('[name=password]').value=${JSON.stringify(PW)};document.querySelector('form').submit()`);
    await done; await sleep(1500);
}
await shot("phone-portal");
await go("/book/?service=clinic-consultation"); await shot("phone-booking");

ws.close();
chrome.kill();

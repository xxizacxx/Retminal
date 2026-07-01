// Serveur d'avancement, accessible sur TOUT le WiFi (0.0.0.0).
// + un bouton GO : POST /go incremente go.count (Claude le surveille).
const http = require("http");
const fs = require("fs");
const path = require("path");
const os = require("os");

const ROOT = __dirname;
const PORT = 8090;
const COUNT = path.join(ROOT, "go.count");
const TYPES = {
  ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8", ".png": "image/png",
  ".svg": "image/svg+xml", ".ico": "image/x-icon",
};

http.createServer((req, res) => {
  const url = req.url.split("?")[0];
  if (url === "/go" && req.method === "POST") {
    let c = 0;
    try { c = parseInt(fs.readFileSync(COUNT, "utf8")) || 0; } catch (e) {}
    c++;
    try { fs.writeFileSync(COUNT, String(c)); } catch (e) {}
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ count: c }));
    return;
  }
  let p = decodeURIComponent(url);
  if (p === "/" || p === "") p = "/index.html";
  const safe = path.normalize(p).replace(/^(\.\.[\/\\])+/, "");
  const file = path.join(ROOT, safe);
  if (!file.startsWith(ROOT)) { res.writeHead(403); res.end("403"); return; }
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404); res.end("404"); return; }
    res.writeHead(200, { "Content-Type": TYPES[path.extname(file).toLowerCase()] || "application/octet-stream" });
    res.end(data);
  });
}).listen(PORT, "0.0.0.0", () => {
  const nets = os.networkInterfaces();
  const ips = [];
  for (const name of Object.keys(nets))
    for (const net of nets[name])
      if (net.family === "IPv4" && !net.internal) ips.push(net.address);
  console.log("=== Avancement Retminal (accessible sur le WiFi) ===");
  console.log("Sur CE PC          : http://localhost:" + PORT);
  ips.forEach((ip) => console.log("Sur tes appareils  : http://" + ip + ":" + PORT));
});

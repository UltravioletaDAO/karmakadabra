// ollama-proxy.js — Injects reasoning_effort:"none" into OpenAI-compatible API calls
// This disables Qwen3/3.5 thinking tokens that OpenClaw can't control
const http = require("http");

const OLLAMA_HOST = process.env.OLLAMA_HOST || "192.168.0.59";
const OLLAMA_PORT = parseInt(process.env.OLLAMA_PORT || "11434");
const LISTEN_PORT = parseInt(process.env.PROXY_PORT || "11434");

const server = http.createServer((req, res) => {
  const isChat = req.url === "/v1/chat/completions" && req.method === "POST";

  let body = [];
  req.on("data", (chunk) => body.push(chunk));
  req.on("end", () => {
    let payload = Buffer.concat(body);

    if (isChat) {
      try {
        const json = JSON.parse(payload.toString());
        // Disable Qwen3/3.5 thinking tokens
        if (!json.reasoning_effort) {
          json.reasoning_effort = "none";
        }
        // Set context window per-request (Ollama supports this in OpenAI endpoint)
        if (!json.options) json.options = {};
        if (!json.options.num_ctx) json.options.num_ctx = 8192;
        const tools = json.tools || [];
        const msgCount = (json.messages || []).length;
        const lastMsg = (json.messages || []).slice(-1)[0];
        const lastRole = lastMsg ? lastMsg.role : "?";
        const lastLen = lastMsg ? JSON.stringify(lastMsg.content).length : 0;
        console.log(`[proxy] model=${json.model} msgs=${msgCount} tools=${tools.length} lastRole=${lastRole} lastLen=${lastLen} ctx=${json.options.num_ctx}`);
        payload = Buffer.from(JSON.stringify(json));
      } catch (_) {}
    }

    const opts = {
      hostname: OLLAMA_HOST,
      port: OLLAMA_PORT,
      path: req.url,
      method: req.method,
      headers: {
        ...req.headers,
        host: `${OLLAMA_HOST}:${OLLAMA_PORT}`,
        "content-length": payload.length,
      },
    };

    const proxy = http.request(opts, (upstream) => {
      res.writeHead(upstream.statusCode, upstream.headers);
      upstream.pipe(res);
    });

    proxy.on("error", (err) => {
      res.writeHead(502);
      res.end(`Proxy error: ${err.message}`);
    });

    proxy.write(payload);
    proxy.end();
  });
});

server.listen(LISTEN_PORT, "0.0.0.0", () => {
  console.log(`[ollama-proxy] Listening on :${LISTEN_PORT} -> ${OLLAMA_HOST}:${OLLAMA_PORT}`);
  console.log(`[ollama-proxy] Injecting reasoning_effort:"none" for /v1/chat/completions`);
});

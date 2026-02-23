/**
 * Karma Kadabra V2 — TypeScript IRC Client
 *
 * Lightweight IRC client for KK agents to communicate on MeshRelay
 * (irc.meshrelay.xyz). Uses Node.js net/tls modules directly.
 *
 * Usage:
 *   import { IRCClient } from "./lib/irc-client";
 *   const client = new IRCClient({ nick: "kk-agent", channels: ["#Agents"] });
 *   await client.connect();
 *   client.send("#Agents", "[HELLO] Online!");
 *   const messages = client.poll();
 *   client.disconnect();
 */

import * as net from "net";
import * as tls from "tls";
import { EventEmitter } from "events";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface IRCConfig {
  server: string;
  port: number;
  tls: boolean;
  tlsPort: number;
  nick: string;
  channels: string[];
  realname: string;
  autoJoin: boolean;
}

export interface IRCMessage {
  raw: string;
  prefix: string;
  nick: string;
  command: string;
  params: string[];
  trailing: string;
  timestamp: number;
  channel: string;
  text: string;
  isPrivate: boolean;
}

export const DEFAULT_CONFIG: IRCConfig = {
  server: "irc.meshrelay.xyz",
  port: 6667,
  tls: false,
  tlsPort: 6697,
  nick: "kk-agent",
  channels: ["#Agents"],
  realname: "Karma Kadabra Agent - Ultravioleta DAO",
  autoJoin: true,
};

// ---------------------------------------------------------------------------
// Parser
// ---------------------------------------------------------------------------

export function parseIRCMessage(raw: string): IRCMessage {
  const msg: IRCMessage = {
    raw,
    prefix: "",
    nick: "",
    command: "",
    params: [],
    trailing: "",
    timestamp: Date.now(),
    channel: "",
    text: "",
    isPrivate: false,
  };

  let line = raw.trim();
  if (!line) return msg;

  // Extract trailing
  const trailIdx = line.indexOf(" :");
  if (trailIdx !== -1) {
    msg.trailing = line.slice(trailIdx + 2);
    line = line.slice(0, trailIdx);
  }

  const parts = line.split(" ");
  let idx = 0;

  // Prefix
  if (parts[0]?.startsWith(":")) {
    msg.prefix = parts[0].slice(1);
    msg.nick = msg.prefix.includes("!")
      ? msg.prefix.split("!")[0]
      : msg.prefix;
    idx = 1;
  }

  if (idx < parts.length) {
    msg.command = parts[idx].toUpperCase();
    idx++;
  }

  msg.params = parts.slice(idx);
  msg.channel = msg.params[0] ?? "";
  msg.text = msg.trailing;
  msg.isPrivate = !!msg.channel && !msg.channel.startsWith("#");

  return msg;
}

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

export class IRCClient extends EventEmitter {
  private config: IRCConfig;
  private socket: net.Socket | tls.TLSSocket | null = null;
  private buffer = "";
  private _connected = false;
  private _registered = false;
  private inbox: IRCMessage[] = [];
  private readCursor = 0;

  constructor(config: Partial<IRCConfig> = {}) {
    super();
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  get connected(): boolean {
    return this._connected;
  }

  get nick(): string {
    return this.config.nick;
  }

  // ----------------------------------------------------------------
  // Connection
  // ----------------------------------------------------------------

  connect(timeout = 15000): Promise<boolean> {
    return new Promise((resolve) => {
      const port = this.config.tls ? this.config.tlsPort : this.config.port;

      const onConnect = () => {
        this._connected = true;
        this.send(`NICK ${this.config.nick}`);
        this.send(`USER ${this.config.nick} 0 * :${this.config.realname}`);
      };

      if (this.config.tls) {
        this.socket = tls.connect(
          { host: this.config.server, port, rejectUnauthorized: false },
          onConnect
        );
      } else {
        this.socket = net.createConnection({ host: this.config.server, port }, onConnect);
      }

      const timer = setTimeout(() => {
        if (!this._registered) {
          this.disconnect();
          resolve(false);
        }
      }, timeout);

      this.socket.setEncoding("utf8");
      this.socket.on("data", (data: string) => {
        this.buffer += data;
        const lines = this.buffer.split("\r\n");
        this.buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.trim()) continue;
          const msg = parseIRCMessage(line);

          if (msg.command === "PING") {
            this.send(`PONG :${msg.trailing}`);
            continue;
          }

          if (msg.command === "001") {
            this._registered = true;
            clearTimeout(timer);

            if (this.config.autoJoin) {
              for (const ch of this.config.channels) {
                this.join(ch);
              }
            }
            resolve(true);
            continue;
          }

          if (msg.command === "433" || msg.command === "436") {
            this.config.nick = `${this.config.nick}-${Date.now() % 10000}`;
            this.send(`NICK ${this.config.nick}`);
            continue;
          }

          if (msg.command === "PRIVMSG" || msg.command === "NOTICE") {
            this.inbox.push(msg);
            this.emit("message", msg);
          }
        }
      });

      this.socket.on("error", (err) => {
        this._connected = false;
        clearTimeout(timer);
        this.emit("error", err);
        resolve(false);
      });

      this.socket.on("close", () => {
        this._connected = false;
        this.emit("close");
      });
    });
  }

  disconnect(): void {
    if (this.socket && this._connected) {
      try {
        this.send("QUIT :Karma Kadabra agent signing off");
      } catch {}
      this.socket.destroy();
    }
    this.socket = null;
    this._connected = false;
    this._registered = false;
  }

  // ----------------------------------------------------------------
  // Channel
  // ----------------------------------------------------------------

  join(channel: string): void {
    if (!channel.startsWith("#")) channel = `#${channel}`;
    this.send(`JOIN ${channel}`);
  }

  part(channel: string, message = "Leaving"): void {
    if (!channel.startsWith("#")) channel = `#${channel}`;
    this.send(`PART ${channel} :${message}`);
  }

  // ----------------------------------------------------------------
  // Messaging
  // ----------------------------------------------------------------

  sendMessage(target: string, message: string): void {
    // IRC line limit ~512 bytes; split at 400 chars
    const chunks = this.splitMessage(message, 400);
    for (const chunk of chunks) {
      this.send(`PRIVMSG ${target} :${chunk}`);
    }
  }

  // ----------------------------------------------------------------
  // Polling
  // ----------------------------------------------------------------

  poll(maxCount = 100): IRCMessage[] {
    const result = this.inbox.slice(this.readCursor, this.readCursor + maxCount);
    this.readCursor += result.length;
    return result;
  }

  pollAll(): IRCMessage[] {
    return this.poll(this.inbox.length);
  }

  tail(count = 10): IRCMessage[] {
    return this.inbox.slice(-count);
  }

  // ----------------------------------------------------------------
  // Internal
  // ----------------------------------------------------------------

  private send(line: string): void {
    if (!this.socket || !this._connected) return;
    this.socket.write(`${line}\r\n`);
  }

  private splitMessage(text: string, maxLen: number): string[] {
    if (text.length <= maxLen) return [text];
    const chunks: string[] = [];
    while (text.length > 0) {
      chunks.push(text.slice(0, maxLen));
      text = text.slice(maxLen);
    }
    return chunks;
  }
}

// ---------------------------------------------------------------------------
// Config loader
// ---------------------------------------------------------------------------

import * as fs from "fs";
import * as path from "path";

export function loadConfig(configPath: string): IRCConfig {
  const raw = fs.readFileSync(configPath, "utf-8");
  const data = JSON.parse(raw);
  return {
    server: data.server ?? DEFAULT_CONFIG.server,
    port: data.port ?? DEFAULT_CONFIG.port,
    tls: data.tls ?? DEFAULT_CONFIG.tls,
    tlsPort: data.tls_port ?? data.port_ssl ?? DEFAULT_CONFIG.tlsPort,
    nick: data.nick ?? DEFAULT_CONFIG.nick,
    channels: data.channels ?? DEFAULT_CONFIG.channels,
    realname: data.realname ?? DEFAULT_CONFIG.realname,
    autoJoin: data.auto_join ?? DEFAULT_CONFIG.autoJoin,
  };
}

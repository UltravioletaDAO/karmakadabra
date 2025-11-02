/// IRC Logging Proof of Concept
///
/// This demonstrates how to integrate IRC logging with tracing-subscriber
/// for real-time log streaming to an IRC channel.
///
/// Usage:
///   IRC_ENABLED=true IRC_SERVER=irc.libera.chat IRC_CHANNEL=#test cargo run
///
/// Then join the IRC channel with your favorite client to see logs appear in real-time.

use irc::client::prelude::*;
use once_cell::sync::Lazy;
use regex::Regex;
use std::env;
use tokio::sync::mpsc;
use tracing::{error, info, warn};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt, Layer};

/// Sanitization patterns for sensitive data
static PRIVATE_KEY_PATTERN: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"0x[a-fA-F0-9]{64}").unwrap());
static API_KEY_PATTERN: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"sk-proj-[A-Za-z0-9_-]+").unwrap());
static ADDRESS_PATTERN: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"(0x[a-fA-F0-9]{10})[a-fA-F0-9]{30,}").unwrap());

/// Sanitize log messages to remove sensitive data
fn sanitize_message(msg: &str) -> String {
    let mut sanitized = msg.to_string();

    // Redact private keys
    sanitized = PRIVATE_KEY_PATTERN
        .replace_all(&sanitized, "0x[REDACTED_KEY]")
        .to_string();

    // Redact API keys
    sanitized = API_KEY_PATTERN
        .replace_all(&sanitized, "sk-[REDACTED]")
        .to_string();

    // Truncate long addresses
    sanitized = ADDRESS_PATTERN
        .replace_all(&sanitized, "$1...")
        .to_string();

    sanitized
}

/// Truncate messages to IRC's 510-byte limit
fn truncate_irc_message(msg: &str) -> String {
    const MAX_LEN: usize = 400; // Leave room for channel name + protocol overhead
    if msg.len() <= MAX_LEN {
        msg.to_string()
    } else {
        format!("{}... [truncated]", &msg[..MAX_LEN])
    }
}

/// Custom tracing layer that forwards logs to IRC
struct IrcLayer {
    tx: mpsc::UnboundedSender<String>,
}

/// Visitor to extract the formatted message from a tracing event
struct MessageVisitor {
    message: String,
}

impl MessageVisitor {
    fn new() -> Self {
        Self {
            message: String::new(),
        }
    }
}

impl tracing::field::Visit for MessageVisitor {
    fn record_debug(&mut self, field: &tracing::field::Field, value: &dyn std::fmt::Debug) {
        if field.name() == "message" {
            self.message = format!("{:?}", value);
            // Remove quotes from debug format
            if self.message.starts_with('"') && self.message.ends_with('"') {
                self.message = self.message[1..self.message.len() - 1].to_string();
            }
        }
    }
}

impl<S> Layer<S> for IrcLayer
where
    S: tracing::Subscriber,
{
    fn on_event(
        &self,
        event: &tracing::Event<'_>,
        _ctx: tracing_subscriber::layer::Context<'_, S>,
    ) {
        let metadata = event.metadata();

        // Only send INFO, WARN, ERROR to IRC (filter out DEBUG/TRACE)
        if !matches!(
            *metadata.level(),
            tracing::Level::INFO | tracing::Level::WARN | tracing::Level::ERROR
        ) {
            return;
        }

        // Extract the actual log message using visitor
        let mut visitor = MessageVisitor::new();
        event.record(&mut visitor);

        // If we got a message, use it; otherwise use target
        let content = if !visitor.message.is_empty() {
            visitor.message
        } else {
            format!("Event in {}", metadata.target())
        };

        // Format the message with level and content
        let msg = format!("[{}] {}", metadata.level(), content);

        // Sanitize and truncate
        let sanitized = sanitize_message(&msg);
        let truncated = truncate_irc_message(&sanitized);

        // Send to IRC channel (non-blocking)
        let _ = self.tx.send(truncated);
    }
}

/// Background task that sends queued messages to IRC
async fn irc_sender_task(
    mut rx: mpsc::UnboundedReceiver<String>,
    channel: String,
    config: Config,
) {
    loop {
        match Client::from_config(config.clone()).await {
            Ok(client) => {
                info!("Connected to IRC server, identifying...");

                if let Err(e) = client.identify() {
                    error!("Failed to identify with IRC server: {}", e);
                    tokio::time::sleep(tokio::time::Duration::from_secs(30)).await;
                    continue;
                }

                info!("Successfully connected to IRC channel: {}", channel);

                // Send a test message to verify channel connectivity
                if let Err(e) = client.send_privmsg(&channel, "IRC logging initialized") {
                    error!("Failed to send initial message to IRC: {}", e);
                    error!("Channel might not exist or bot might be banned");
                    tokio::time::sleep(tokio::time::Duration::from_secs(30)).await;
                    continue;
                }

                // Message sending loop with rate limiting
                while let Some(msg) = rx.recv().await {
                    // Rate limiting: 1 message per 500ms = 2 msg/sec (safe)
                    tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;

                    if let Err(e) = client.send_privmsg(&channel, &msg) {
                        error!("Failed to send IRC message '{}': {}", msg, e);
                        // Connection lost, break and reconnect
                        break;
                    } else {
                        // Successfully sent, log to console for debugging
                        println!("[IRC->{}] {}", channel, msg);
                    }
                }
            }
            Err(e) => {
                error!("IRC connection failed: {}, retrying in 30s...", e);
                tokio::time::sleep(tokio::time::Duration::from_secs(30)).await;
            }
        }
    }
}

/// Initialize tracing with optional IRC layer
fn init_tracing() {
    let irc_layer = if env::var("IRC_ENABLED").is_ok() {
        let (tx, rx) = mpsc::unbounded_channel();

        let server = env::var("IRC_SERVER").unwrap_or_else(|_| "irc.dal.net".to_string());
        let channel = env::var("IRC_CHANNEL").unwrap_or_else(|_| "#karmacadabra".to_string());
        let nickname =
            env::var("IRC_NICK").unwrap_or_else(|_| "x402-poc".to_string());
        let use_tls = env::var("IRC_TLS").map(|v| v == "true").unwrap_or(true);

        let config = Config {
            nickname: Some(nickname.clone()),
            server: Some(server.clone()),
            channels: vec![channel.clone()],
            use_tls: Some(use_tls),
            ..Default::default()
        };

        // Spawn background IRC sender
        tokio::spawn(irc_sender_task(rx, channel.clone(), config));

        println!(
            "IRC logging enabled: {}:{} as {}",
            server, channel, nickname
        );

        Some(IrcLayer { tx })
    } else {
        println!("IRC logging disabled (set IRC_ENABLED=true to enable)");
        None
    };

    // Build subscriber with console + optional IRC layer
    let subscriber = tracing_subscriber::registry()
        .with(tracing_subscriber::filter::LevelFilter::INFO)
        .with(tracing_subscriber::fmt::layer());

    if let Some(irc_layer) = irc_layer {
        subscriber.with(irc_layer).init();
    } else {
        subscriber.init();
    }
}

#[tokio::main]
async fn main() {
    // Initialize logging (console + IRC if enabled)
    init_tracing();

    info!("Starting IRC logging proof of concept...");

    // Simulate some application activity
    for i in 1..=10 {
        tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;

        match i {
            1..=3 => info!("Processing request #{}", i),
            4 => warn!("High load detected, request #{}", i),
            5 => {
                // Simulate logging with sensitive data
                let fake_key = "0x1234567890123456789012345678901234567890123456789012345678901234";
                info!(
                    "Payment from address {} using key {}",
                    "0x2C3E6F8A9B1234567890ABCDEF1234567890ABCD", fake_key
                );
            }
            6 => error!("Failed to connect to RPC endpoint"),
            7..=9 => info!("Recovered, processing request #{}", i),
            10 => info!("Shutting down gracefully..."),
            _ => {}
        }
    }

    // Give time for queued IRC messages to send
    tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;
    info!("Proof of concept complete!");
}

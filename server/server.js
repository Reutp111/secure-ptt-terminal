const WebSocket = require("ws");

const PORT = 3000;
const wss = new WebSocket.Server({ port: PORT });

const clients = new Map();

/*
clients:
ws => {
  userId: string,
  channel: string,
  connectedAt: Date
}
*/

function sendJson(ws, data) {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(data));
  }
}

function broadcastToChannel(channel, senderWs, payload) {
  for (const [clientWs, clientData] of clients.entries()) {
    if (
      clientWs !== senderWs &&
      clientData.channel === channel &&
      clientWs.readyState === WebSocket.OPEN
    ) {
      sendJson(clientWs, payload);
    }
  }
}

function getUsersInChannel(channel) {
  const users = [];

  for (const [, clientData] of clients.entries()) {
    if (clientData.channel === channel) {
      users.push(clientData.userId);
    }
  }

  return users;
}

wss.on("connection", (ws) => {
  console.log("[AUDIT] New client connected");

  ws.on("message", (rawMessage) => {
    let message;

    try {
      message = JSON.parse(rawMessage.toString());
    } catch (error) {
      sendJson(ws, {
        type: "error",
        message: "Invalid JSON format",
      });
      return;
    }

    if (message.type === "join") {
      const userId = String(message.userId || "").trim();
      const channel = String(message.channel || "").trim();

      if (!userId || !channel) {
        sendJson(ws, {
          type: "error",
          message: "Missing userId or channel",
        });
        return;
      }

      clients.set(ws, {
        userId,
        channel,
        connectedAt: new Date(),
      });

      console.log(`[AUDIT] user_connected user=${userId} channel=${channel}`);

      sendJson(ws, {
        type: "joined",
        userId,
        channel,
        users: getUsersInChannel(channel),
      });

      broadcastToChannel(channel, ws, {
        type: "system",
        message: `${userId} joined the channel`,
        users: getUsersInChannel(channel),
      });

      return;
    }

    if (message.type === "text-message") {
      const clientData = clients.get(ws);

      if (!clientData) {
        sendJson(ws, {
          type: "error",
          message: "Join a channel first",
        });
        return;
      }

      const text = String(message.text || "").trim();

      if (!text) {
        return;
      }

      if (text.length > 500) {
        sendJson(ws, {
          type: "error",
          message: "Message is too long. Max 500 characters.",
        });
        return;
      }

      /*
        Important:
        The server does NOT save message content.
        It only forwards the message to connected clients in the same channel.
      */
      console.log(
        `[AUDIT] message_relayed from=${clientData.userId} channel=${clientData.channel} length=${text.length}`
      );

      broadcastToChannel(clientData.channel, ws, {
        type: "text-message",
        from: clientData.userId,
        text,
        sentAt: new Date().toISOString(),
      });

      sendJson(ws, {
        type: "delivery-status",
        status: "sent",
      });

      return;
    }

    sendJson(ws, {
      type: "error",
      message: "Unknown message type",
    });
  });

  ws.on("close", () => {
    const clientData = clients.get(ws);

    if (clientData) {
      clients.delete(ws);

      console.log(
        `[AUDIT] user_disconnected user=${clientData.userId} channel=${clientData.channel}`
      );

      broadcastToChannel(clientData.channel, ws, {
        type: "system",
        message: `${clientData.userId} left the channel`,
        users: getUsersInChannel(clientData.channel),
      });
    }
  });

  ws.on("error", () => {
    const clientData = clients.get(ws);

    if (clientData) {
      console.log(
        `[AUDIT] client_error user=${clientData.userId} channel=${clientData.channel}`
      );
    }
  });
});

console.log(`Secure PTT Relay running on ws://localhost:${PORT}`);
console.log("No message content is stored by the server.");
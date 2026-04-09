const http = require("http");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const { URL } = require("url");

function loadDotEnv() {
  const envPath = path.join(__dirname, ".env");
  if (!fs.existsSync(envPath)) return;

  const content = fs.readFileSync(envPath, "utf8");
  for (const rawLine of content.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;

    const separatorIndex = line.indexOf("=");
    if (separatorIndex < 0) continue;

    const key = line.slice(0, separatorIndex).trim();
    const value = line.slice(separatorIndex + 1).trim();
    if (!(key in process.env)) {
      process.env[key] = value;
    }
  }
}

loadDotEnv();

const PORT = Number(process.env.PORT || 8080);
const NODE_ENV = process.env.NODE_ENV || "development";
const APP_URL = process.env.APP_URL || `http://localhost:${PORT}`;
const AUTH_SECRET = process.env.AUTH_SECRET || "";
const ADMIN_USER = process.env.ADMIN_USER || "admin";
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || "";
const WORKER_SECRET = process.env.WORKER_SECRET || "";
const MAX_UPLOAD_MB = Number(process.env.MAX_UPLOAD_MB || 20);

const ROOT = __dirname;
const DATA_DIR = process.env.DATA_DIR ? path.resolve(process.env.DATA_DIR) : path.join(ROOT, "data");
const UPLOADS_DIR = path.join(DATA_DIR, "uploads");
const DB_FILE = path.join(DATA_DIR, "store.json");

const DEFAULTS = {
  authSecret: "change-this-secret",
  adminPassword: "admin123",
  workerSecret: "worker-secret"
};

const allowedMedia = {
  "image/jpeg": "jpg",
  "image/png": "png",
  "image/webp": "webp",
  "video/mp4": "mp4",
  "video/webm": "webm"
};

function nowIso() {
  return new Date().toISOString();
}

function validateEnvironment() {
  const problems = [];

  if (!AUTH_SECRET || AUTH_SECRET === DEFAULTS.authSecret) {
    problems.push("AUTH_SECRET");
  }

  if (!WORKER_SECRET || WORKER_SECRET === DEFAULTS.workerSecret) {
    problems.push("WORKER_SECRET");
  }

  if (!ADMIN_PASSWORD || ADMIN_PASSWORD === DEFAULTS.adminPassword) {
    problems.push("ADMIN_PASSWORD");
  }

  if (NODE_ENV === "production" && problems.length > 0) {
    throw new Error(
      `Variaveis obrigatorias ausentes ou inseguras em producao: ${problems.join(", ")}`
    );
  }
}

function createEmptyDb() {
  return {
    settings: {
      timezone: "America/Sao_Paulo",
      integrations: {
        instagram: { mode: "mock", connected: false, accountId: "" },
        facebook: { mode: "mock", connected: false, pageId: "" },
        whatsapp: { mode: "mock", connected: false, phoneNumberId: "" }
      }
    },
    users: [],
    posts: [],
    logs: []
  };
}

function writeDb(db) {
  fs.writeFileSync(DB_FILE, JSON.stringify(db, null, 2));
}

function readDb() {
  return JSON.parse(fs.readFileSync(DB_FILE, "utf8"));
}

function createUserRecord(username, password, role) {
  const salt = crypto.randomBytes(16).toString("hex");
  const passwordHash = hashPassword(password, salt);

  return {
    id: crypto.randomUUID(),
    username,
    passwordHash,
    salt,
    role,
    createdAt: nowIso()
  };
}

function logEvent(level, message, postId = null) {
  return {
    id: crypto.randomUUID(),
    level,
    message,
    postId,
    timestamp: nowIso()
  };
}

function ensureStorage() {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  fs.mkdirSync(UPLOADS_DIR, { recursive: true });

  if (!fs.existsSync(DB_FILE)) {
    writeDb(createEmptyDb());
  }

  const db = readDb();
  if (!Array.isArray(db.users)) db.users = [];
  if (!Array.isArray(db.posts)) db.posts = [];
  if (!Array.isArray(db.logs)) db.logs = [];
  if (!db.settings || typeof db.settings !== "object") {
    db.settings = createEmptyDb().settings;
  }

  if (db.users.length === 0) {
    db.users.push(createUserRecord(ADMIN_USER, ADMIN_PASSWORD || DEFAULTS.adminPassword, "admin"));
    db.logs.push(logEvent("info", `Usuario admin seed criado: ${ADMIN_USER}`));
    writeDb(db);
    return;
  }

  writeDb(db);
}

function hashPassword(password, salt) {
  return crypto.pbkdf2Sync(password, salt, 100000, 64, "sha512").toString("hex");
}

function safeEqual(a, b) {
  const left = Buffer.from(a);
  const right = Buffer.from(b);
  if (left.length !== right.length) return false;
  return crypto.timingSafeEqual(left, right);
}

function verifyPassword(password, user) {
  return safeEqual(hashPassword(password, user.salt), user.passwordHash);
}

function signToken(payload) {
  const body = Buffer.from(JSON.stringify(payload)).toString("base64url");
  const signature = crypto.createHmac("sha256", AUTH_SECRET).update(body).digest("base64url");
  return `${body}.${signature}`;
}

function verifyToken(token) {
  if (!token || !token.includes(".")) return null;

  const [body, signature] = token.split(".");
  const expected = crypto.createHmac("sha256", AUTH_SECRET).update(body).digest("base64url");
  if (!safeEqual(signature, expected)) return null;

  const payload = JSON.parse(Buffer.from(body, "base64url").toString("utf8"));
  if (payload.exp < Date.now()) return null;
  return payload;
}

function parseAuth(req) {
  const authHeader = req.headers.authorization || "";
  const token = authHeader.startsWith("Bearer ") ? authHeader.slice(7) : null;
  return verifyToken(token);
}

function json(res, status, payload) {
  res.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(payload));
}

function text(res, status, body) {
  res.writeHead(status, { "Content-Type": "text/plain; charset=utf-8" });
  res.end(body);
}

function readBody(req, maxBytes = 25 * 1024 * 1024) {
  return new Promise((resolve, reject) => {
    let raw = "";

    req.on("data", (chunk) => {
      raw += chunk;
      if (raw.length > maxBytes) {
        reject(new Error("Payload muito grande"));
      }
    });

    req.on("end", () => {
      if (!raw) return resolve({});
      try {
        resolve(JSON.parse(raw));
      } catch {
        reject(new Error("JSON invalido"));
      }
    });

    req.on("error", reject);
  });
}

function sanitizePostInput(input, timezone) {
  const caption = String(input.caption || "").trim();
  const scheduledAt = String(input.scheduledAt || "");
  const networks = Array.isArray(input.networks) ? input.networks.filter(Boolean) : [];
  const media = input.media || null;

  if (!caption) throw new Error("Legenda e obrigatoria");
  if (caption.length > 2200) throw new Error("Legenda excedeu 2200 caracteres");
  if (networks.length === 0) throw new Error("Selecione ao menos uma rede social");
  if (!media || !media.path) throw new Error("Midia e obrigatoria");

  const when = new Date(scheduledAt);
  if (Number.isNaN(when.getTime())) throw new Error("Data/hora invalida");
  if (when.getTime() <= Date.now()) throw new Error("Nao e permitido agendar no passado");

  return {
    caption,
    scheduledAt: when.toISOString(),
    timezone: timezone || "UTC",
    networks,
    media,
    maxAttempts: 3,
    retryCount: 0,
    status: "agendado",
    publishLogs: [],
    createdAt: nowIso(),
    updatedAt: nowIso()
  };
}

function listPosts(db, filters) {
  let items = [...db.posts];
  if (filters.status) items = items.filter((post) => post.status === filters.status);
  if (filters.network) items = items.filter((post) => post.networks.includes(filters.network));
  return items.sort((a, b) => new Date(a.scheduledAt) - new Date(b.scheduledAt));
}

async function publishToNetworkMock(post, network) {
  const draw = Math.random();
  await new Promise((resolve) => setTimeout(resolve, 200));

  if (draw < 0.75) {
    return { ok: true, externalId: `${network}_${crypto.randomUUID().slice(0, 8)}` };
  }

  if (draw < 0.95) {
    return { ok: false, temporary: true, error: `Falha temporaria em ${network}` };
  }

  return { ok: false, temporary: false, error: `Falha permanente em ${network}` };
}

async function processDuePosts(trigger = "interval") {
  const db = readDb();
  const now = Date.now();
  const duePosts = db.posts.filter((post) => {
    if (!["agendado", "erro"].includes(post.status)) return false;
    if (post.nextRetryAt && new Date(post.nextRetryAt).getTime() > now) return false;
    return new Date(post.scheduledAt).getTime() <= now;
  });

  for (const post of duePosts) {
    post.status = "publicando";
    post.updatedAt = nowIso();
    writeDb(db);

    let temporaryFailure = false;
    let permanentFailure = false;
    const attempts = [];

    for (const network of post.networks) {
      const result = await publishToNetworkMock(post, network);
      attempts.push({ network, ...result, at: nowIso() });
      if (!result.ok && result.temporary) temporaryFailure = true;
      if (!result.ok && !result.temporary) permanentFailure = true;
    }

    post.retryCount += 1;
    post.publishLogs.push(...attempts);

    if (!temporaryFailure && !permanentFailure) {
      post.status = "publicado";
      post.publishedAt = nowIso();
      post.errorMessage = "";
      delete post.nextRetryAt;
      db.logs.push(logEvent("info", `Post ${post.id} publicado com sucesso (${trigger})`, post.id));
    } else if (temporaryFailure && post.retryCount < post.maxAttempts) {
      const waitSeconds = 30 * Math.pow(2, post.retryCount - 1);
      post.status = "erro";
      post.errorMessage = "Falha temporaria. Novo retry agendado.";
      post.nextRetryAt = new Date(Date.now() + waitSeconds * 1000).toISOString();
      db.logs.push(
        logEvent("warn", `Post ${post.id} falhou temporariamente. Retry em ${waitSeconds}s`, post.id)
      );
    } else {
      post.status = "erro";
      post.errorMessage = permanentFailure
        ? "Falha permanente de publicacao"
        : "Limite de tentativas atingido";
      delete post.nextRetryAt;
      db.logs.push(logEvent("error", `Post ${post.id} finalizado com erro`, post.id));
    }

    post.updatedAt = nowIso();
    writeDb(db);
  }
}

function requireAuth(req, res) {
  const session = parseAuth(req);
  if (!session) {
    json(res, 401, { error: "Nao autenticado" });
    return null;
  }
  return session;
}

function serveStatic(req, res, pathname) {
  const target = pathname === "/" ? "/index.html" : pathname;
  const normalized = path.normalize(target).replace(/^\.\.(\/|\\|$)/, "");
  const fullPath = path.join(ROOT, normalized);

  if (!fullPath.startsWith(ROOT)) return text(res, 403, "Forbidden");
  if (!fs.existsSync(fullPath) || fs.statSync(fullPath).isDirectory()) return text(res, 404, "Not found");

  const ext = path.extname(fullPath).toLowerCase();
  const mime =
    {
      ".html": "text/html; charset=utf-8",
      ".css": "text/css; charset=utf-8",
      ".js": "application/javascript; charset=utf-8",
      ".json": "application/json; charset=utf-8",
      ".svg": "image/svg+xml",
      ".png": "image/png",
      ".jpg": "image/jpeg",
      ".jpeg": "image/jpeg",
      ".webp": "image/webp",
      ".mp4": "video/mp4",
      ".webm": "video/webm"
    }[ext] || "application/octet-stream";

  res.writeHead(200, { "Content-Type": mime });
  fs.createReadStream(fullPath).pipe(res);
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, APP_URL);
  const pathname = url.pathname;

  try {
    if (req.method === "GET" && pathname === "/health") {
      return json(res, 200, { ok: true, time: nowIso() });
    }

    if (req.method === "POST" && pathname === "/api/auth/login") {
      const body = await readBody(req);
      const username = String(body.username || "").trim();
      const password = String(body.password || "");
      const db = readDb();
      const user = db.users.find((item) => item.username === username);

      if (!user || !verifyPassword(password, user)) {
        return json(res, 401, { error: "Credenciais invalidas" });
      }

      const token = signToken({
        sub: user.id,
        username: user.username,
        role: user.role,
        exp: Date.now() + 1000 * 60 * 60 * 8
      });
      db.logs.push(logEvent("info", `Login realizado por ${user.username}`));
      writeDb(db);
      return json(res, 200, { token, user: { username: user.username, role: user.role } });
    }

    if (req.method === "POST" && pathname === "/api/worker/tick") {
      const body = await readBody(req);
      if (body.secret !== WORKER_SECRET) {
        return json(res, 403, { error: "Segredo invalido" });
      }
      await processDuePosts("manual-tick");
      return json(res, 200, { ok: true });
    }

    if (pathname.startsWith("/api/")) {
      const session = requireAuth(req, res);
      if (!session) return;

      await processDuePosts("api-catchup");

      if (req.method === "GET" && pathname === "/api/me") {
        return json(res, 200, { user: session });
      }

      if (req.method === "GET" && pathname === "/api/settings") {
        const db = readDb();
        return json(res, 200, db.settings);
      }

      if (req.method === "PUT" && pathname === "/api/settings") {
        const body = await readBody(req);
        const db = readDb();
        db.settings.timezone = String(body.timezone || db.settings.timezone || "UTC");
        db.settings.integrations = body.integrations || db.settings.integrations;
        db.logs.push(logEvent("info", `Configuracoes atualizadas por ${session.username}`));
        writeDb(db);
        return json(res, 200, db.settings);
      }

      if (req.method === "POST" && pathname === "/api/upload") {
        const body = await readBody(req, 35 * 1024 * 1024);
        const dataUrl = String(body.dataUrl || "");
        const originalName = String(body.fileName || "arquivo").replace(/[^a-zA-Z0-9_.-]/g, "_");
        const match = dataUrl.match(/^data:([^;]+);base64,(.+)$/);
        if (!match) {
          return json(res, 400, { error: "Formato de upload invalido. Use data URL base64." });
        }

        const mime = match[1];
        const base64Payload = match[2];
        if (!allowedMedia[mime]) {
          return json(res, 400, { error: "Tipo de arquivo nao permitido" });
        }

        const buffer = Buffer.from(base64Payload, "base64");
        const maxBytes = MAX_UPLOAD_MB * 1024 * 1024;
        if (buffer.length > maxBytes) {
          return json(res, 400, { error: `Arquivo excede ${MAX_UPLOAD_MB}MB` });
        }

        const ext = allowedMedia[mime];
        const mediaId = crypto.randomUUID();
        const fileName = `${mediaId}.${ext}`;
        const relativePath = path.join("data", "uploads", fileName).replaceAll("\\", "/");
        fs.writeFileSync(path.join(ROOT, relativePath), buffer);

        return json(res, 201, {
          id: mediaId,
          fileName: originalName,
          mime,
          size: buffer.length,
          path: `/${relativePath}`
        });
      }

      if (req.method === "GET" && pathname === "/api/posts") {
        const db = readDb();
        const status = url.searchParams.get("status") || "";
        const network = url.searchParams.get("network") || "";
        return json(res, 200, listPosts(db, { status, network }));
      }

      if (req.method === "POST" && pathname === "/api/posts") {
        const body = await readBody(req);
        const db = readDb();
        const sanitized = sanitizePostInput(body, db.settings.timezone);
        const post = {
          id: crypto.randomUUID(),
          ...sanitized,
          createdBy: session.username
        };
        db.posts.push(post);
        db.logs.push(logEvent("info", `Post ${post.id} agendado por ${session.username}`, post.id));
        writeDb(db);
        return json(res, 201, post);
      }

      if (req.method === "PUT" && pathname.startsWith("/api/posts/")) {
        const postId = pathname.split("/").pop();
        const body = await readBody(req);
        const db = readDb();
        const post = db.posts.find((item) => item.id === postId);
        if (!post) return json(res, 404, { error: "Post nao encontrado" });
        if (post.status === "publicado") {
          return json(res, 400, { error: "Post ja publicado nao pode ser editado" });
        }

        const updated = sanitizePostInput(body, db.settings.timezone);
        Object.assign(post, updated, {
          id: post.id,
          retryCount: 0,
          publishLogs: [],
          errorMessage: "",
          updatedAt: nowIso()
        });
        delete post.publishedAt;
        delete post.nextRetryAt;
        db.logs.push(logEvent("info", `Post ${post.id} atualizado por ${session.username}`, post.id));
        writeDb(db);
        return json(res, 200, post);
      }

      if (req.method === "DELETE" && pathname.startsWith("/api/posts/")) {
        const postId = pathname.split("/").pop();
        const db = readDb();
        const index = db.posts.findIndex((item) => item.id === postId);
        if (index < 0) return json(res, 404, { error: "Post nao encontrado" });

        const [removed] = db.posts.splice(index, 1);
        db.logs.push(logEvent("warn", `Post ${removed.id} removido por ${session.username}`, removed.id));
        writeDb(db);
        return json(res, 200, { success: true });
      }

      if (req.method === "GET" && pathname === "/api/logs") {
        const db = readDb();
        const logs = [...db.logs]
          .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
          .slice(0, 200);
        return json(res, 200, logs);
      }

      return json(res, 404, { error: "Endpoint nao encontrado" });
    }

    return serveStatic(req, res, pathname);
  } catch (error) {
    return json(res, 500, { error: error.message || "Erro interno" });
  }
});

validateEnvironment();
ensureStorage();

setInterval(() => {
  processDuePosts("interval").catch(() => null);
}, 30000);

server.listen(PORT, () => {
  console.log(`Servidor iniciado em ${APP_URL}`);
});

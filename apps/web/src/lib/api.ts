let runtimeApiBaseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL || "/api/v1").replace(/\/$/, "");

export interface ApiRequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  accessToken?: string | null;
}

export type ApiRequester = <T>(path: string, options?: ApiRequestOptions) => Promise<T>;

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

export function getApiBaseUrl(): string {
  return runtimeApiBaseUrl;
}

export function setApiBaseUrl(nextBaseUrl: string): void {
  runtimeApiBaseUrl = nextBaseUrl.replace(/\/$/, "");
}

export function buildQuery(params: Record<string, string | number | boolean | null | undefined>): string {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }
    searchParams.set(key, String(value));
  });
  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : "";
}

function normalizeUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  return `${runtimeApiBaseUrl}${path.startsWith("/") ? path : `/${path}`}`;
}

function parseErrorMessage(data: unknown, fallback: string): string {
  if (typeof data === "string" && data.trim()) {
    return data;
  }
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
  }
  return fallback;
}

function isJsonPayload(body: unknown): boolean {
  if (body === null || body === undefined) {
    return false;
  }
  return !(body instanceof FormData) && typeof body === "object";
}

function buildStationName(): string {
  if (typeof window === "undefined") {
    return "server-render";
  }
  const nav = navigator as Navigator & { userAgentData?: { platform?: string } };
  const platform = nav.userAgentData?.platform || navigator.platform;
  return [window.location.hostname || "browser", platform].filter(Boolean).join(" | ");
}

export async function requestJson<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const { body, accessToken, headers, ...rest } = options;
  const requestHeaders = new Headers(headers || {});

  requestHeaders.set("Accept", "application/json");
  requestHeaders.set("X-Station-Name", buildStationName());

  let finalBody: BodyInit | undefined;
  if (body !== undefined) {
    if (isJsonPayload(body)) {
      requestHeaders.set("Content-Type", "application/json");
      finalBody = JSON.stringify(body);
    } else {
      finalBody = body as BodyInit;
    }
  }

  if (accessToken) {
    requestHeaders.set("Authorization", `Bearer ${accessToken}`);
  }

  const response = await fetch(normalizeUrl(path), {
    ...rest,
    headers: requestHeaders,
    body: finalBody
  });

  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    throw new ApiError(parseErrorMessage(data, `Erro HTTP ${response.status}`), response.status, data);
  }

  return data as T;
}

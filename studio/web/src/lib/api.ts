// Studio API client. Every call is a same-origin POST with JSON and the per-run token the
// server writes into the page; the server refuses anything else.
export interface ApiResult<T = any> { status: number; ok: boolean; data: T }

function token(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="bot-ui-token"]')?.content ?? "";
}

export async function api<T = any>(path: string, body: unknown = {}, signal?: AbortSignal): Promise<ApiResult<T>> {
  let res: Response;
  try {
    res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Bot-UI-Token": token() },
      body: JSON.stringify(body),
      credentials: "same-origin",
      cache: "no-store",
      signal,
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    return { status: 0, ok: false, data: { error: { code: "OFFLINE", message: "the Studio server does not answer; is `bot-ui studio` still running?" } } as T };
  }
  let data: any;
  try {
    data = await res.json();
  } catch {
    data = { error: { code: "BAD_RESPONSE", message: `HTTP ${res.status} without JSON` } };
  }
  return { status: res.status, ok: res.ok, data };
}

export const errorText = (data: any): string =>
  data?.error ? `${data.error.code}: ${data.error.message ?? ""}` : "unknown error";

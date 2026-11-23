/* Mini App kit: a thin, dependency-free layer over window.Telegram.WebApp ("TMA profile 1").
   Erasable TypeScript only (no enums, namespaces or parameter properties): Node >= 22.18 runs it
   directly in tests, and build.mjs strips the types for the browser.
   What it does: saves launch params before a router can erase them; mirrors scheme, platform and the
   Android performance class onto <html>; gates every call by version; drives the MainButton,
   SecondaryButton and BackButton from a screen stack; haptics by meaning; storage with fallbacks;
   events with unsubscribe. Reference: references/mini-apps/design-system.md, webapp-api.md. */

export type Scheme = 'light' | 'dark';
export type PlatformClass = 'ios' | 'android' | 'desktop' | 'web' | 'unknown';
export type Perf = 'low' | 'average' | 'high' | 'unknown';
export type ChromeColor = 'bg_color' | 'secondary_bg_color' | 'bottom_bar_bg_color' | `#${string}`;

export interface BottomButtonLike {
  setParams(p: Record<string, unknown>): unknown;
  onClick(cb: () => void): unknown;
  offClick(cb: () => void): unknown;
  showProgress(leaveActive?: boolean): unknown;
  hideProgress(): unknown;
  isVisible?: boolean;
}

export interface WebAppLike {
  initData: string;
  version: string;
  platform?: string;
  colorScheme?: Scheme;
  themeParams?: Record<string, string>;
  isVersionAtLeast(v: string): boolean;
  ready(): void;
  expand?(): void;
  close?(): void;
  onEvent(name: string, cb: (...a: unknown[]) => void): void;
  offEvent(name: string, cb: (...a: unknown[]) => void): void;
  setHeaderColor?(c: string): void;
  setBackgroundColor?(c: string): void;
  setBottomBarColor?(c: string): void;
  enableClosingConfirmation?(): void;
  disableClosingConfirmation?(): void;
  showConfirm?(msg: string, cb: (ok: boolean) => void): void;
  showPopup?(p: Record<string, unknown>, cb: (id: string) => void): void;
  MainButton?: BottomButtonLike;
  SecondaryButton?: BottomButtonLike;
  BackButton?: { show(): void; hide(): void; onClick(cb: () => void): void; offClick(cb: () => void): void };
  SettingsButton?: { show(): void; hide(): void; onClick(cb: () => void): void; offClick(cb: () => void): void };
  HapticFeedback?: {
    impactOccurred(s: string): void;
    notificationOccurred(t: string): void;
    selectionChanged(): void;
  };
  CloudStorage?: StorageLike;
  DeviceStorage?: StorageLike;
  SecureStorage?: StorageLike;
}

interface StorageLike {
  setItem(k: string, v: string, cb?: (err: unknown, ok?: unknown) => void): void;
  getItem(k: string, cb: (err: unknown, v?: string | null) => void): void;
  removeItem(k: string, cb?: (err: unknown, ok?: unknown) => void): void;
}

export interface RootLike {
  dataset: Record<string, string | undefined>;
  style: { setProperty(name: string, value: string): void; colorScheme?: string };
}

export interface FallbackButtonLike {
  hidden: boolean;
  textContent: string | null;
  disabled?: boolean;
  onclick: ((ev?: unknown) => unknown) | null;
}

export interface Env {
  webApp?: WebAppLike | null;
  /** Shown instead of the MainButton outside Telegram (plain browser); default: [data-tma-fallback="main-button"]. */
  fallbackButton?: FallbackButtonLike | null;
  root?: RootLike;
  location?: { hash: string; search: string };
  userAgent?: string;
}

/* ------------------------------------------------------------ pure helpers (unit-tested) */

/** "7.10" >= "7.2": numeric per part, like Telegram.WebApp.isVersionAtLeast. */
export function versionAtLeast(have: string, need: string): boolean {
  const a = have.split('.').map(Number);
  const b = need.split('.').map(Number);
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    const x = a[i] || 0;
    const y = b[i] || 0;
    if (x !== y) return x > y;
  }
  return true;
}

/** Android's User-Agent ends with "Telegram-Android/<ver> (<maker model>; Android <v>; SDK <n>; <CLASS>)". */
export function perfClass(userAgent: string): Perf {
  const m = userAgent.match(/Telegram-Android\/\S+ \([^)]*;\s*(LOW|AVERAGE|HIGH)\)/);
  return m ? (m[1].toLowerCase() as Perf) : 'unknown';
}

export function platformClass(platform: string | undefined): PlatformClass {
  if (!platform) return 'unknown';
  if (platform === 'ios') return 'ios';
  if (platform === 'android' || platform === 'android_x') return 'android';
  if (platform === 'tdesktop' || platform === 'macos' || platform === 'unigram') return 'desktop';
  if (platform.startsWith('web')) return 'web';
  return 'unknown';
}

/** Launch params live in location.hash (tgWebApp*) and start_param also in the query. Read them once,
    on the first line of the app, before a hash router rewrites the hash. */
export function readLaunchParams(loc: { hash: string; search: string }): Record<string, string> {
  const out: Record<string, string> = {};
  const hash = new URLSearchParams(loc.hash.replace(/^#/, ''));
  hash.forEach((v, k) => { if (k.startsWith('tgWebApp')) out[k] = v; });
  const start = new URLSearchParams(loc.search).get('tgWebAppStartParam');
  if (start !== null && !out.tgWebAppStartParam) out.tgWebAppStartParam = start;
  return out;
}

/** start_param is attacker-controlled text: accept only the patterns the app routes. */
export function parseStartParam(raw: string | undefined, routes: Record<string, RegExp>): { route: string; match: RegExpMatchArray } | null {
  if (!raw || !/^[A-Za-z0-9_-]{1,512}$/.test(raw)) return null;
  for (const [route, re] of Object.entries(routes)) {
    const match = raw.match(re);
    if (match) return { route, match };
  }
  return null;
}

/* ------------------------------------------------------------ the kit */

export interface MainButtonSpec {
  text: string;
  onClick: () => void | Promise<void>;
  active?: boolean;
  color?: string;
  textColor?: string;
  shine?: boolean;
  iconCustomEmojiId?: string; // 9.5+; ignored on older clients
}

export interface SecondaryButtonSpec extends MainButtonSpec {
  position?: 'left' | 'right' | 'top' | 'bottom';
}

export interface Layer {
  id: string;
  kind: 'screen' | 'sheet';
  onBack?: () => void;
}

export function createTma(env: Env = {}) {
  const w = (typeof window !== 'undefined' ? window : undefined) as unknown as
    { Telegram?: { WebApp?: WebAppLike }; location?: Location; navigator?: Navigator; document?: Document } | undefined;
  const tg: WebAppLike | null = env.webApp !== undefined ? env.webApp : (w?.Telegram?.WebApp ?? null);
  const root: RootLike | undefined = env.root ?? (w?.document?.documentElement as unknown as RootLike | undefined);
  const launch = readLaunchParams(env.location ?? w?.location ?? { hash: '', search: '' });
  const ua = env.userAgent ?? w?.navigator?.userAgent ?? '';
  const inTelegram = !!tg && typeof tg.initData === 'string' && tg.initData.length > 0;
  const has = (v: string): boolean => !!tg && typeof tg.isVersionAtLeast === 'function' && tg.isVersionAtLeast(v);
  const subs: Array<() => void> = [];

  function on(name: string, cb: (...a: unknown[]) => void): () => void {
    if (!tg) return () => {};
    tg.onEvent(name, cb);
    const off = () => tg.offEvent(name, cb);
    subs.push(off);
    return off;
  }

  /* -- scheme, platform, performance class on <html> */
  function syncRoot(): void {
    if (!root) return;
    const scheme = tg?.colorScheme;
    if (scheme) {
      root.dataset.tmaScheme = scheme;
      root.style.colorScheme = scheme;
    }
    root.dataset.tmaPlatform = platformClass(tg?.platform);
    root.dataset.tmaPerf = perfClass(ua);
  }

  /* -- chrome colours: keywords follow the theme; literals are re-applied on themeChanged */
  let chromeSpec: { header?: ChromeColor; background?: ChromeColor; bottomBar?: ChromeColor } = {};
  function applyChrome(): void {
    if (!tg) return;
    if (chromeSpec.header && has('6.1')) tg.setHeaderColor?.(chromeSpec.header);
    if (chromeSpec.background && has('6.1')) tg.setBackgroundColor?.(chromeSpec.background);
    if (chromeSpec.bottomBar && has('7.10')) tg.setBottomBarColor?.(chromeSpec.bottomBar);
  }
  function chrome(spec: typeof chromeSpec): void {
    chromeSpec = { ...chromeSpec, ...spec };
    applyChrome();
  }

  syncRoot();
  on('themeChanged', () => { syncRoot(); applyChrome(); });

  /* -- haptics by meaning (table in design-system.md); silent below 6.1 */
  const haptic = {
    select(): void { if (has('6.1')) tg?.HapticFeedback?.selectionChanged(); },
    tap(): void { if (has('6.1')) tg?.HapticFeedback?.impactOccurred('light'); },
    success(): void { if (has('6.1')) tg?.HapticFeedback?.notificationOccurred('success'); },
    warning(): void { if (has('6.1')) tg?.HapticFeedback?.notificationOccurred('warning'); },
    error(): void { if (has('6.1')) tg?.HapticFeedback?.notificationOccurred('error'); },
  };

  /* -- bottom buttons: one spec per screen; progress while the handler runs */
  function bindBottom(btn: BottomButtonLike | undefined, spec: MainButtonSpec | null, extra: Record<string, unknown>,
                      prev: { cb: (() => void) | null }, flag?: string): void {
    if (!btn) return;
    if (prev.cb) btn.offClick(prev.cb);
    prev.cb = null;
    if (!spec) {
      btn.setParams({ is_visible: false });
      if (flag && root) root.dataset[flag] = 'hidden';
      return;
    }
    const params: Record<string, unknown> = { text: spec.text, is_visible: true, is_active: spec.active !== false, ...extra };
    if (spec.color) params.color = spec.color;
    if (spec.textColor) params.text_color = spec.textColor;
    if (spec.shine !== undefined && has('7.10')) params.has_shine_effect = spec.shine;
    if (spec.iconCustomEmojiId && has('9.5')) params.icon_custom_emoji_id = spec.iconCustomEmojiId;
    btn.setParams(params);
    const cb = async () => {
      haptic.tap();
      btn.showProgress(false);
      try { await spec.onClick(); } finally { btn.hideProgress(); }
    };
    prev.cb = () => { void cb(); };
    btn.onClick(prev.cb);
    if (flag && root) root.dataset[flag] = 'visible';
  }
  const fallback: FallbackButtonLike | null = env.fallbackButton !== undefined ? env.fallbackButton
    : ((w?.document?.querySelector('[data-tma-fallback="main-button"]') as unknown as FallbackButtonLike | null) ?? null);
  function bindFallback(spec: MainButtonSpec | null): void {
    if (!fallback) return;
    fallback.hidden = !spec;
    fallback.textContent = spec ? spec.text : '';
    fallback.disabled = spec ? spec.active === false : true;
    fallback.onclick = spec ? () => { void spec.onClick(); } : null;
  }
  const mainPrev = { cb: null as (() => void) | null };
  const secondaryPrev = { cb: null as (() => void) | null };
  function mainButton(spec: MainButtonSpec | null): void {
    if (!inTelegram) bindFallback(spec);
    bindBottom(tg?.MainButton, spec, {}, mainPrev, 'tmaMainButton');
  }
  /** SecondaryButton is 7.10+. Returns false on older clients: render the action in the content instead. */
  function secondaryButton(spec: SecondaryButtonSpec | null): boolean {
    if (!has('7.10')) return false;
    bindBottom(tg?.SecondaryButton, spec, spec?.position ? { position: spec.position } : {}, secondaryPrev);
    return true;
  }

  /* -- one navigation stack: screens and sheets; BackButton mirrors its depth */
  const stack: Layer[] = [];
  const backHandler = () => {
    const top = stack[stack.length - 1];
    if (top) top.onBack?.();
  };
  if (tg?.BackButton && has('6.1')) tg.BackButton.onClick(backHandler);
  subs.push(() => { if (tg?.BackButton && has('6.1')) tg.BackButton.offClick(backHandler); });
  function syncBack(): void {
    if (!tg?.BackButton || !has('6.1')) return;
    if (stack.length > 0) tg.BackButton.show();
    else tg.BackButton.hide();
  }
  const nav = {
    push(layer: Layer): void { stack.push(layer); syncBack(); },
    pop(id?: string): Layer | undefined {
      const i = id ? stack.map((l) => l.id).lastIndexOf(id) : stack.length - 1;
      const [removed] = i >= 0 ? stack.splice(i, 1) : [];
      syncBack();
      return removed;
    },
    reset(): void { stack.length = 0; syncBack(); },
    get depth(): number { return stack.length; },
    get top(): Layer | undefined { return stack[stack.length - 1]; },
  };

  /* -- settings item in the ⋯ menu (7.0+) */
  function settings(cb: (() => void) | null): void {
    if (!tg?.SettingsButton || !has('7.0')) return;
    if (cb) { tg.SettingsButton.onClick(cb); tg.SettingsButton.show(); subs.push(() => tg.SettingsButton?.offClick(cb)); }
    else tg.SettingsButton.hide();
  }

  /* -- unsaved input */
  function closingConfirmation(on: boolean): void {
    if (!has('6.2')) return;
    if (on) tg?.enableClosingConfirmation?.();
    else tg?.disableClosingConfirmation?.();
  }

  /* -- native confirm (6.2+); the caller supplies an in-content fallback */
  function confirm(message: string, fallback: () => Promise<boolean>): Promise<boolean> {
    if (tg?.showConfirm && has('6.2')) {
      return new Promise((resolve) => tg.showConfirm!(message, (ok) => resolve(!!ok)));
    }
    return fallback();
  }

  /* -- storage: promise wrappers; null when the client has no such storage */
  function wrap(s: StorageLike | undefined, since: string) {
    if (!s || !has(since)) return null;
    return {
      get: (k: string) => new Promise<string | null>((res, rej) => s.getItem(k, (e, v) => (e ? rej(e) : res(v ?? null)))),
      set: (k: string, v: string) => new Promise<void>((res, rej) => s.setItem(k, v, (e) => (e ? rej(e) : res()))),
      remove: (k: string) => new Promise<void>((res, rej) => s.removeItem(k, (e) => (e ? rej(e) : res()))),
    };
  }
  /** Non-secret data synced across the user's devices: CloudStorage (6.9); in memory outside Telegram.
      Never localStorage. DeviceStorage (9.0) and SecureStorage (9.0) are below. */
  const mem = new Map<string, string>();
  function store() {
    const native = wrap(tg?.CloudStorage, '6.9');
    if (native) return native;
    return {
      get: async (k: string) => mem.get(k) ?? null,
      set: async (k: string, v: string) => { mem.set(k, v); },
      remove: async (k: string) => { mem.delete(k); },
    };
  }
  const deviceStore = () => wrap(tg?.DeviceStorage, '9.0');
  const secureStore = () => wrap(tg?.SecureStorage, '9.0');

  /** Call once the first useful screen is drawn (Telegram then hides its loading screen). */
  function ready(): void { tg?.ready(); }

  function dispose(): void {
    mainButton(null);
    if (has('7.10')) secondaryButton(null);
    while (subs.length) subs.pop()!();
  }

  return {
    tg, inTelegram, launch, has, on, chrome, haptic, mainButton, secondaryButton, nav, settings,
    closingConfirmation, confirm, store, deviceStore, secureStore, ready, dispose,
    get initData(): string { return tg?.initData ?? ''; },
  };
}

export type Tma = ReturnType<typeof createTma>;

// One prompt for the user's coding agent, built from saved-but-uncommitted files, queued requests
// and (optionally) an exported patch. Pure function: the Task view previews and copies its output.
export type PromptLang = "en" | "ru" | "uk";

export interface PromptInput {
  lang: PromptLang;
  title: string;
  projectPath: string;
  locales: string[];
  saved: { path: string; status: string; screenId?: string; widgetId?: string }[];
  diff?: string;
  requests: { sid: string | null; text: string }[];
  patchFile?: string;
  draftScreens?: string[];
  /** The project's premium emoji library (emoji/library.json), when it has icons or packs. */
  emoji?: { route: string; packs: string[]; icons: { slot: string; id: string; fallback: string }[]; unknown: number };
}

const T = {
  en: {
    task: (t: string, p: string) => `Task: update the Telegram bot interface of "${t}" (bot-ui project \`${p}\`, contract: studio/docs/contract.md).`,
    saved: "Already saved to files by the bot-ui Studio (not committed, not deployed). Review them and wire them into the bot code where needed:",
    status: { M: "changed", A: "new", D: "deleted", "??": "new" } as Record<string, string>,
    requests: "Requested changes (make them through bot-ui):",
    general: "general",
    screen: "screen",
    widget: "widget",
    patch: (f: string) => `First apply the exported patch \`${f}\`: \`bot-ui apply-patch --project ${"{p}"} --patch-file ${f}\` (it refuses to overwrite newer edits; on a conflict re-read and redo the change).`,
    drafts: (ids: string) => `The patch contains unsaved Studio drafts for: ${ids}.`,
    rules: "Rules:",
    rule: [
      "Change screens only through the bot-ui project: `bot-ui show <screenId> --json`, then edit, `bot-ui validate`, `bot-ui simulate --all`; write with `--expected-revision` (or `apply-patch`) so newer edits are never overwritten.",
      "Keep screen IDs, action IDs, callback_data, {placeholders} and every locale ({locales}); fill missing translations.",
      "Review the adapter and the handlers for new or changed actions, rules and handler outcomes.",
      "Commit on a new branch (for example ui/<topic>). Do not push to production and do not deploy.",
      "Finish with a short report per screen ID: what changed and how you checked it.",
    ],
    diff: "Diff of the saved changes (bot-ui folder vs HEAD):",
    empty: "Nothing to hand off yet: save a change or queue a request first.",
    emoji: (n: number, packs: string, route: string) => `Premium emoji: the bot's icon map is in \`emoji/library.json\` (${n} meanings; packs: ${packs}; capabilities.customEmoji = ${route}). Before placing custom emoji run \`bot-ui emoji brief\` and follow it: only these ids, chosen by meaning; \`<tg-emoji emoji-id="ID">FALLBACK</tg-emoji>\` in texts with the map's fallback, \`"icon": {"customEmojiId": "ID"}\` on buttons (no emoji at the label start); then \`audit_icons.py emoji/library.json\` from the skill.`,
    emojiNone: "capabilities.customEmoji is none: Telegram drops custom emoji from this bot silently; do not rely on them until the owner confirms Fragment usernames or Premium.",
    emojiUnknown: (n: number) => `${n} custom emoji in the screens are not in the library: check or replace them (listed by \`bot-ui emoji brief\`).`,
  },
  ru: {
    task: (t: string, p: string) => `Задача: обновить интерфейс Telegram-бота «${t}» (проект bot-ui \`${p}\`, контракт: studio/docs/contract.md).`,
    saved: "Уже сохранено в файлы через bot-ui Studio (не закоммичено, не задеплоено). Проверь и подключи в коде бота, где нужно:",
    status: { M: "изменён", A: "новый", D: "удалён", "??": "новый" } as Record<string, string>,
    requests: "Что нужно изменить (через bot-ui):",
    general: "общее",
    screen: "экран",
    widget: "виджет",
    patch: (f: string) => `Сначала примени экспортированный патч \`${f}\`: \`bot-ui apply-patch --project ${"{p}"} --patch-file ${f}\` (он не перезапишет более новые правки; при конфликте перечитай и повтори изменение).`,
    drafts: (ids: string) => `В патче несохранённые черновики Studio для: ${ids}.`,
    rules: "Правила:",
    rule: [
      "Меняй экраны только через проект bot-ui: `bot-ui show <screenId> --json`, затем правка, `bot-ui validate`, `bot-ui simulate --all`; записывай с `--expected-revision` (или `apply-patch`), чтобы не затереть более новые правки.",
      "Сохраняй ID экранов и действий, callback_data, {плейсхолдеры} и все локали ({locales}); дополни недостающие переводы.",
      "Проверь адаптер и обработчики для новых или изменённых действий, правил и исходов обработчиков.",
      "Закоммить в новую ветку (например ui/<тема>). Не пушь в прод и не деплой.",
      "В конце коротко отчитайся по каждому ID экрана: что изменено и как проверено.",
    ],
    diff: "Diff сохранённых изменений (папка bot-ui относительно HEAD):",
    empty: "Пока нечего передавать: сохрани изменение или добавь запрос.",
    emoji: (n: number, packs: string, route: string) => `Премиум-эмодзи: карта иконок бота в \`emoji/library.json\` (${n} значений; паки: ${packs}; capabilities.customEmoji = ${route}). Перед расстановкой custom emoji выполни \`bot-ui emoji brief\` и следуй ему: только эти ID, по смыслу; в тексте \`<tg-emoji emoji-id="ID">FALLBACK</tg-emoji>\` с fallback из карты, на кнопках \`"icon": {"customEmojiId": "ID"}\` (без эмодзи в начале подписи); затем \`audit_icons.py emoji/library.json\` из скилла.`,
    emojiNone: "capabilities.customEmoji = none: Telegram молча убирает custom emoji у этого бота; не полагайся на них, пока владелец не подтвердит Fragment-юзернеймы или Premium.",
    emojiUnknown: (n: number) => `${n} custom emoji в экранах нет в библиотеке: проверь или замени их (список в \`bot-ui emoji brief\`).`,
  },
  uk: {
    task: (t: string, p: string) => `Завдання: оновити інтерфейс Telegram-бота «${t}» (проєкт bot-ui \`${p}\`, контракт: studio/docs/contract.md).`,
    saved: "Уже збережено у файли через bot-ui Studio (не закомічено, не задеплоєно). Перевір і підключи в коді бота, де потрібно:",
    status: { M: "змінено", A: "новий", D: "видалено", "??": "новий" } as Record<string, string>,
    requests: "Що потрібно змінити (через bot-ui):",
    general: "загальне",
    screen: "екран",
    widget: "віджет",
    patch: (f: string) => `Спершу застосуй експортований патч \`${f}\`: \`bot-ui apply-patch --project ${"{p}"} --patch-file ${f}\` (він не перезапише новіші правки; у разі конфлікту перечитай і повтори зміну).`,
    drafts: (ids: string) => `У патчі незбережені чернетки Studio для: ${ids}.`,
    rules: "Правила:",
    rule: [
      "Змінюй екрани лише через проєкт bot-ui: `bot-ui show <screenId> --json`, потім правка, `bot-ui validate`, `bot-ui simulate --all`; записуй з `--expected-revision` (або `apply-patch`), щоб не затерти новіші правки.",
      "Зберігай ID екранів і дій, callback_data, {плейсхолдери} та всі локалі ({locales}); доповни відсутні переклади.",
      "Перевір адаптер і обробники для нових або змінених дій, правил і результатів обробників.",
      "Закоміть у нову гілку (наприклад ui/<тема>). Не пуш у прод і не деплой.",
      "Наприкінці коротко звітуй по кожному ID екрана: що змінено і як перевірено.",
    ],
    diff: "Diff збережених змін (папка bot-ui відносно HEAD):",
    empty: "Поки нічого передавати: збережи зміну або додай запит.",
    emoji: (n: number, packs: string, route: string) => `Преміум-емодзі: карта іконок бота в \`emoji/library.json\` (${n} значень; паки: ${packs}; capabilities.customEmoji = ${route}). Перед розстановкою custom emoji виконай \`bot-ui emoji brief\` і дотримуйся його: лише ці ID, за змістом; у тексті \`<tg-emoji emoji-id="ID">FALLBACK</tg-emoji>\` з fallback із карти, на кнопках \`"icon": {"customEmojiId": "ID"}\` (без емодзі на початку підпису); потім \`audit_icons.py emoji/library.json\` зі скіла.`,
    emojiNone: "capabilities.customEmoji = none: Telegram мовчки прибирає custom emoji у цього бота; не покладайся на них, доки власник не підтвердить Fragment-юзернейми або Premium.",
    emojiUnknown: (n: number) => `${n} custom emoji в екранах немає в бібліотеці: перевір або заміни їх (список у \`bot-ui emoji brief\`).`,
  },
};

export function buildPrompt(i: PromptInput): string {
  const t = T[i.lang];
  if (!i.saved.length && !i.requests.length && !i.patchFile) return t.empty;
  const out: string[] = [t.task(i.title, i.projectPath), ""];
  let n = 1;
  if (i.patchFile) {
    out.push(`${n++}. ${t.patch(i.patchFile).replace("{p}", i.projectPath)}`);
    if (i.draftScreens?.length) out.push(`   ${t.drafts(i.draftScreens.join(", "))}`);
    out.push("");
  }
  if (i.saved.length) {
    out.push(`${n++}. ${t.saved}`);
    for (const f of i.saved) {
      const what = f.screenId ? `${t.screen} ${f.screenId}` : f.widgetId ? `${t.widget} ${f.widgetId}` : "";
      out.push(`   - ${what ? `${what}: ` : ""}${f.path} (${t.status[f.status] ?? f.status})`);
    }
    out.push("");
  }
  if (i.requests.length) {
    out.push(`${n++}. ${t.requests}`);
    for (const r of i.requests) out.push(`   - ${r.sid ?? t.general}: ${r.text.replace(/\s*\n\s*/g, " ")}`);
    out.push("");
  }
  if (i.emoji && (i.emoji.icons.length || i.emoji.packs.length)) {
    out.push(`${n++}. ${t.emoji(i.emoji.icons.length, i.emoji.packs.join(", ") || "-", i.emoji.route)}`);
    for (const ic of i.emoji.icons) out.push(`   - ${ic.slot}: ${ic.id} (${ic.fallback || "-"})`);
    if (i.emoji.route === "none") out.push(`   ${t.emojiNone}`);
    if (i.emoji.unknown) out.push(`   ${t.emojiUnknown(i.emoji.unknown)}`);
    out.push("");
  }
  out.push(t.rules);
  for (const r of t.rule) out.push(`- ${r.replace("{locales}", i.locales.join(", "))}`);
  if (i.diff) out.push("", t.diff, "```diff", i.diff.replace(/\n$/, ""), "```");
  return out.join("\n") + "\n";
}

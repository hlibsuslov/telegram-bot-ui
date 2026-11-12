# Recipe index (Bot API 10.3 / 10.4)

Find a recipe by task, API symbol, version or context. Machine-readable: `manifest.json`
(recipes → registry rows, symbols, files) and `registry.json` (every changelog item).
All recipes run offline: `py -3 examples/python/recipes/<file>.py`; TypeScript twins:
`node examples/ts/recipes.ts`, tests `cd examples/ts && npm test`.

| Recipe | Typical request | Symbols | Version | Context |
|---|---|---|---|---|
| [01 AI assistant + Stop](01-ai-assistant.md) | "stream the answer, let me stop it" | `sendRichMessageDraft`, `can_stop`, `keep_on_stop`, `stopped_message_generation` | 10.3 | private (+topics) |
| [02 Interactive document](02-interactive-document.md) | "send it as a proper document with a button / attached PDF / answer the quoted line" | `RichMessageButton`, `RichTextButton`, `<tg-button-row>`, `is_compact`, `expandable_blockquote`, `tg-document`, `tg://document`, `quote_rich_texts`, `RichTextTonAddress` | 10.3, 10.4 | any rich-capable chat |
| [03 Multi-step form](03-multi-step-form.md) | "pick or type", "people double-tap Submit" | `force_reply` (inline/reply markup), `DisabledButton` | 10.3 | private, groups |
| [04 Shared card + personal panel](04-shared-card-personal-panel.md) | "private answer in the group", "don't show my order to everyone" | `EphemeralMessageParameters`, `replace_callback_query_message`, `editEphemeralMessage*` | 10.3, 10.4 | groups (not channel DMs) |
| [05 Private widget](05-private-widget.md) | "one card that updates", "interactive order card" | `sendWidget`, `widget_query`, `answerWidgetQuery`, `editMessageWidgetData`, `Widget` | 10.4 | **private (production)** |
| [06 Shared widget](06-shared-widget.md) | "live poll everywhere" | `sendSharedWidget`, `editSharedWidgetData`, `shared_widget_query`, `InputWidgetMessageContent` | 10.4 | private; forwards/inline/groups **test server** |
| [07 Wallet](07-wallet.md) | "pay in TON in the chat", "link my wallet" | `WidgetQueryType*`, `WidgetQueryWallet`, `TonWalletCard`, `TonWalletTransfer`, `ton_address`, `AreaPosition` | 10.4 | private |
| [08 Multi-topic bot](08-multi-topic-bot.md) | "answers mix between topics", "link to another topic" | `message_thread_id`, `t.me/<bot>/<thread>`, `direct_messages_topic_id` | 10.3, 10.4 | private topics, forum, channel DMs |
| [09 Tracker bot (btc-tracker upgrade)](09-tracker-bot.md) | "one card per transaction", "live price", "our icons look mismatched" | `sendWidget`, `editMessageWidgetData`, `sendSharedWidget`, `cache_time`, `is_compact`, `disabled`, `force_reply`, `icon_custom_emoji_id` | 9.4, 10.3, 10.4 | private (widgets), any (fallback) |
| [Mini-recipes](mini-recipes.md) | welcome, community joins, gift notes, `getUniqueGift`, `deleteBusinessAccountGift`, share themes, managed bot usernames, verification, paid messages waived, card masking, renames | see table | 10.3, 10.4 | mixed |

Combining features is normal: a group lunch bot = 04 (personal panel) + 03 (form for the order)
+ 06 (poll in private chats); a support assistant = 01 + 08 + 02 (quote the policy line).

By bot type (monitoring, AI assistant, shop, team utility, support, docs, wallet, games): `references/bot-archetypes.md`.

# 93 — Mini App shop: catalogue → product → cart → checkout

Product recipe (no registry row). Verified 2026-11-23 against Bot API 10.5. Payments depth:
`references/payments-and-stars.md` (this recipe does not change payment logic, it shows where the Mini App
hands over). Layout: `references/mini-apps/layout-rules.md`. Tags: **[API]**, **[official]**, **[heuristic]**.

1. **Request and visible result.** “Turn our coffee shop bot into a proper store with photos and a cart.” —
   A catalogue grid (or a menu list with photos at the end), product screens with variants, a cart with
   steppers, “Checkout · €8.40” in the MainButton, Telegram's payment sheet, and the receipt as a bot
   message.
2. **Why these features.** Prices are computed on the server from item ids; the client's price is ignored
   **[heuristic]**. Digital goods are sold in Stars (`XTR`, one price) **[official]**; `createInvoiceLink`
   on the server + `WebApp.openInvoice` in the app **[API]/[official]**; the order is paid only on
   `successful_payment`, never on `invoiceClosed` **[official]**. Cards and tiles follow L02-L08 (image
   ratio, title → meta → price, sold out visible) **[heuristic]**.
3. **Requirements.** Bot API ≥ 6.1 for `openInvoice`; private chat for the receipt; `allowed_updates` with
   `pre_checkout_query` and `message` (payments recipe 20) **[API]**.
4. **Payload.** `examples/payloads/r93-mini-app-shop.json`: `createInvoiceLink` (XTR, one price) and the
   receipt `sendMessage` after `successful_payment`.
5. **Code.** Server and bot: `r90_99_mini_apps.py::r93` (`price_cart`). App: `examples/mini-apps/vanilla`
   (menu rows, item detail with MainButton, cart steppers) and `examples/mini-apps/catalog` (Books: grid of
   2:3 covers, detail with format selector and `Add to cart · €12.90`). Payment flow details: recipe 20.
6. **Sequence and state.**
   ```mermaid
   sequenceDiagram
     participant A as Mini App
     participant S as Server
     participant T as Telegram
     A->>S: cart (ids, sizes, quantities) + initData
     S->>S: price the cart, create order o:1042
     S->>T: createInvoiceLink (XTR)
     S-->>A: invoice link
     A->>T: openInvoice(link)
     T->>S: pre_checkout_query → answer (≤ 10 s)
     T->>S: successful_payment → receipt message, order paid
   ```
7. **Result.** Mock: grid tile `[cover] The Quiet Harbour / Mira Kovac / €12.90`; MainButton
   `Add to cart · €12.90`; after paying, the chat shows “Paid ⭐ 420. Order 1042: 2 × Flat white, pickup
   10:30.”
8. **Typical mistake, limits, alternative.** Prices from the client; fulfilling on `invoiceClosed: paid`;
   several price parts for Stars; hiding sold-out items; a buy button on every card (L19); a checkout that
   asks for the name Telegram already gave. Alternative: a message shop (recipe 20) for ≤ 5 items.
9. **Run and verify.** `py -3 examples/python/recipes/r90_99_mini_apps.py r93` (3 self-checks) ·
   `py -3 scripts/miniapp_layout.py review <your catalogue spec>` · lint and the preview matrix. Evidence:
   offline contract; real payments not executed.
10. **Adapt.** Keep: server pricing, one invoice per order, fulfilment on `successful_payment`, the receipt
    in the chat. Replace: `MENU` with your catalogue and stock. Related: recipes 20 (payments), 52 (widget to
    checkout), 95 (dashboard after purchase).

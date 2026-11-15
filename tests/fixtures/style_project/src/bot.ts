import { Bot, InlineKeyboard } from "grammy";

const bot = new Bot(process.env.BOT_TOKEN ?? "");
const home = new InlineKeyboard()
  .text("Open catalogue", "cat:open")
  .row()
  .text("Track my orders", "orders:list");
await bot.api.setMyCommands([{ command: "start", description: "Open the shop" }]);
const confirm = { text: "Pay", callback_data: "pay:1", style: "primary" };
bot.on("callback_query:data", (ctx) => ctx.answerCallbackQuery());
export { home, confirm };

import { Bot } from "grammy";

const bot = new Bot("TOKEN");

const commands = [
  { command: "start", description: "Open the main menu" },
  { command: "help", description: "How the bot works" },
];

bot.command("start", (ctx) => ctx.reply("Hi"));
bot.command(["help", "about"], (ctx) => ctx.reply("Help"));
// bot.command("legacy", (ctx) => ctx.reply("gone"));

await bot.api.setMyCommands(commands);
await bot.api.setMyCommands(
  [{ command: "start", description: "Открыть меню" }],
  { scope: { type: "all_private_chats" }, language_code: "ru" },
);

bot.start();

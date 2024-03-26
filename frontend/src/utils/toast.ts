import { toast } from "@zerodevx/svelte-toast";

export enum Level {
  info = "info",
  warn = "warn",
}

export function showToast(
  level: Level,
  message: string = undefined,
  args = {}
) {
  if (message === undefined) {
    message = level == Level.info ? "Success" : "Failed";
  }
  toast.push(message, { classes: [level], ...args });
}

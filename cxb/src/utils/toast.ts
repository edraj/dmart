import { toast } from "@zerodevx/svelte-toast";

export enum Level {
  info = "info",
  warn = "warn",
  success = "success",
  error = "error",
  warning = "warning",
  informative = "informative",
}

const DEFAULTS: Record<Level, string> = {
  [Level.info]: "Success",
  [Level.success]: "Success",
  [Level.warn]: "Failed",
  [Level.error]: "Failed",
  [Level.warning]: "Warning",
  [Level.informative]: "Info",
};

export function showToast(level: Level, message?: string, args = {}) {
  const text = message ?? DEFAULTS[level];
  toast.push(text, { classes: [level], ...args });
}

export const toastSuccess = (message?: string, args = {}) =>
  showToast(Level.success, message, args);
export const toastError = (message?: string, args = {}) =>
  showToast(Level.error, message, args);
export const toastWarning = (message?: string, args = {}) =>
  showToast(Level.warning, message, args);
export const toastInfo = (message?: string, args = {}) =>
  showToast(Level.informative, message, args);

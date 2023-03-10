import { toast } from "@zerodevx/svelte-toast";

export function toastPushSuccess(message = "Success") {
  toast.push(message, {
    theme: {
      "--toastColor": "mintcream",
      "--toastBackground": "rgba(72,187,120,0.9)",
      "--toastBarBackground": "#2F855A",
    },
  });
}

export function toastPushFail(message = "Failed!") {
  toast.push(message, {
    theme: {
      "--toastColor": "mintcream",
      "--toastBackground": "#bb4848e6",
      "--toastBarBackground": "#852f2f",
    },
  });
}

import {Level, showToast} from "@/utils/toast";

function debounce<T extends (...args: never[]) => void>(func: T, delay: number): (...args: Parameters<T>) => void {
    let timeoutId: ReturnType<typeof setTimeout>;
    return (...args: Parameters<T>) => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func(...args), delay);
    };
}

export const debouncedShowToast = debounce((level: Level, message: string) => {
    showToast(level, message);
}, 300);

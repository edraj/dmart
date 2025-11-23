import {showToast} from "@/utils/toast";

function debounce(func: (...args: any[]) => void, delay: number) {
    let timeoutId;
    return (...args: any[]) => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func(...args), delay);
    };
}

export const debouncedShowToast = debounce((level, message) => {
    showToast(level, message);
}, 300);
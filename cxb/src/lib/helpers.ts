export function formatDate(dateString: string): string {
    const date = new Date(dateString);

    const yyyy = date.getFullYear();
    const mm = String(date.getMonth() + 1).padStart(2, '0');
    const dd = String(date.getDate()).padStart(2, '0');
    const hh = String(date.getHours()).padStart(2, '0');
    const MM = String(date.getMinutes()).padStart(2, '0');

    return `${yyyy}-${mm}-${dd} ${hh}:${MM}`;
}

export function truncateString(str: string, maxLength = 100): string {
    return str && str.length > maxLength ? str.slice(0, maxLength) + "..." : str;
}

interface StatefulEntity {
    is_active?: boolean;
    state?: string;
}

const STATE_LABELS: Record<string, string> = {
    pending: "Pending",
    in_progress: "In Progress",
    approved: "Approved",
    rejected: "Rejected",
};

const STATE_ICONS: Record<string, string> = {
    pending: "bi bi-hourglass text-primary",
    in_progress: "bi bi-arrow-repeat text-warning",
    approved: "bi bi-check-lg text-success",
    rejected: "bi bi-x-lg text-danger",
};

export function renderStateString(entity: StatefulEntity): string {
    if (entity.is_active === false) {
        return "Inactive";
    }
    return (entity.state && STATE_LABELS[entity.state]) || "N/A";
}

export function renderStateIcon(entity: StatefulEntity): string {
    if (entity.is_active === false) {
        return "bi bi-x-circle text-secondary";
    }
    return (entity.state && STATE_ICONS[entity.state]) || "N/A";
}

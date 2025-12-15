export function formatDate(dateString: string): string {
    const date = new Date(dateString);

    const yyyy = date.getFullYear();
    const mm = String(date.getMonth() + 1).padStart(2, '0'); // Months are 0-based
    const dd = String(date.getDate()).padStart(2, '0');
    const hh = String(date.getHours()).padStart(2, '0');
    const MM = String(date.getMinutes()).padStart(2, '0');

    return `${yyyy}-${mm}-${dd} ${hh}:${MM}`;
}

export function truncateString(str: string): string {
    return str && str.length > 100 ? str.slice(0, 100) + "..." : str;
}

export function renderStateString(entity: any){
    if (entity.is_active === false) {
        return "Inactive";
    }
    if(entity.state === "pending" ){
        return "Pending";
    }
    if(entity.state === "in_progress" ){
        return "In Progress";
    }
    if(entity.state === "approved" ){
        return "Approved";
    }
    if(entity.state === "rejected" ){
        return "Rejected";
    }
    return "N/A";
}

export function renderStateIcon(entity: any): string {
    if (entity.is_active === false) {
        return "bi bi-x-circle text-secondary";
    }
    if(entity.state === "pending" ){
        return "bi bi-hourglass text-primary";
    }
    if(entity.state === "in_progress" ){
        return "bi bi-arrow-repeat text-warning";
    }
    if(entity.state === "approved" ){
        return "bi bi-check-lg text-success";
    }
    if(entity.state === "rejected" ){
        return "bi bi-x-lg text-danger";
    }
    return "N/A";
}

export function getParentPath(path: string): string {
    if (path === "/") {
        return path;
    }
    const parts = path.split("/");
    parts.pop();
    return parts.join("/") || "/";
}
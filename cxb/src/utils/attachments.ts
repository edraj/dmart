export async function parseCSV(data: string): Promise<{ headers: string[]; rows: Record<string, string | null>[] }> {
    const lines = data.trim().split('\n');
    lines.shift();
    const headers = lines[0].split(',');

    const rows = lines.slice(1).map(line => {
        const values = line.split(',');
        return headers.reduce<Record<string, string | null>>((obj, header, index) => {
            obj[header] = values[index] || null;
            return obj;
        }, {});
    });
    return { headers, rows };
}

function pyToJs(value: string): string {
    const r = value.replaceAll(": True", ": true")
        .replaceAll(": False", ": false").trim();
    if (r.endsWith(",")) {
        return r.substring(0, r.length - 1);
    }
    return r;
}

export function parseJSONL(data: string): Record<string, unknown>[] {
    const lines = data.split('\n');
    return lines.filter(Boolean).map((line, index) => {
        try {
            return JSON.parse(pyToJs(line));
        } catch {
            throw new Error(`Invalid JSON on line ${index + 1}: ${line.slice(0, 80)}`);
        }
    });
}
interface CSVParseResult {
    headers: string[];
    rows: Record<string, string | null>[];
}

export async function parseCSV(data: string): Promise<CSVParseResult> {
    const lines = data.trim().split('\n');
    // Remove BOM or metadata line if present
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

function pyToJs(input: string): string {
    const r = input.replaceAll(": True", ": true")
        .replaceAll(": False", ": false").trim();
    if (r.endsWith(",")) {
        return r.substring(0, r.length - 1);
    }
    return r;
}

export function parseJSONL(data: string): unknown[] {
    const lines = data.split('\n');
    return lines.filter(Boolean).map(line => JSON.parse(pyToJs(line)));
}

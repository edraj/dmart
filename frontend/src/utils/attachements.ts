export async function parseCSV(data) {
    const lines = data.trim().split('\n');
    lines.shift()
    const headers = lines[0].split(',');

    const rows = lines.slice(1).map(line => {
        const values = line.split(',');
        return headers.reduce((obj, header, index) => {
            obj[header] = values[index] || null;
            return obj;
        }, {});
    });
    return { headers, rows };
}

export function parseJSONL(data) {
    const lines = data.trim().split('\n');
    return lines.map(line => JSON.parse(line));
}
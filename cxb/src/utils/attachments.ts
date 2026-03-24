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

function pyTOjs(string){
    const r = string.replaceAll(": True", ": true")
        .replaceAll(": False", ": false").trim();
    if (r.endsWith(",")){
        return r.substring(0, r.length - 1);
    }
    return r;
}

export function parseJSONL(data) {
    const lines = data.split('\n');
    return lines.filter(Boolean).map(line => JSON.parse(pyTOjs(line)));
}
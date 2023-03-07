
export default async function dmart_fetch(url, request) {
  let response = await window.fetch(url, request);
  const reader = response.body.getReader();
  var td = new TextDecoder("utf-8");
  var chunks = [];
  var total_length = 0;
  while (true) {
    const result = await reader.read();
    if (result.done) {
      break;
    } else {
      chunks.push(result.value);
      total_length += result.value.length;
    }
  }
  let data = new Uint8Array(total_length);
  let position = 0;
  for (let chunk of chunks) {
    data.set(chunk, position);
    position += chunk.length;
  }

  let decoded = td.decode(data);
  return JSON.parse(decoded);
}

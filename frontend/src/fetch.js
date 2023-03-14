export default async function dmart_fetch(url, request, type = "json") {
  let response = await fetch(url, request);
  switch (type) {
    case "json":
      return await response.json();
    case "blob":
      return URL.createObjectURL(await response.blob());
    default:
      break;
  }
}

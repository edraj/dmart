export default async function dmartFetch(url, request, type = "json") {
  let response = await fetch(url, request);
  switch (type) {
    case "all":
      return response;
    case "json":
      return await response.json();
    case "blob":
      return URL.createObjectURL(await response.blob());
    default:
      break;
  }
}

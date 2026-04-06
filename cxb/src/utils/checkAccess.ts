export function checkAccess(
  action: string,
  space: string,
  subpath: string,
  resourceType: string
) {
  const keys = [
    `${space}:__all_subpaths__:${resourceType}`,
    `__all_spaces__:__all_subpaths__:${resourceType}`,
    `${space}:${subpath}:${resourceType}`,
  ];

  let permissions: Record<string, { allowed_actions: string[] }> = {};
  if (typeof localStorage !== "undefined") {
    try {
      permissions = JSON.parse(localStorage.getItem("permissions") || "{}") || {};
    } catch {
      return false;
    }
  }
  if (Object.keys(permissions).length === 0) {
    return false;
  }

  const oks: boolean[] = [];
  for (const key of keys) {
    if (permissions[key]) {
      oks.push(permissions[key].allowed_actions.includes(action));
    }
  }

  return oks.some((s) => s);
}
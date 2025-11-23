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

  let permissions = {};
  if (typeof localStorage !== "undefined"){
    permissions = JSON.parse(localStorage.getItem("permissions"));
  }
  if (permissions === null || Object.keys(permissions).length === 0) {
    return false;
  }

  const oks = [];
  for (const key of keys) {
    if (permissions[key]) {
      oks.push(permissions[key].allowed_actions.includes(action));
    }
  }

  return oks.some((s)=>s);
}

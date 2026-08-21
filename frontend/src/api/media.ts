export function snapSrc(path?: string | null): string | undefined {
  if (!path) return undefined;
  const token = localStorage.getItem("gusip.session");
  if (!token) return path;
  try {
    const t = JSON.parse(token).token;
    const join = path.includes("?") ? "&" : "?";
    return `${path}${join}token=${encodeURIComponent(t)}`;
  } catch {
    return path;
  }
}

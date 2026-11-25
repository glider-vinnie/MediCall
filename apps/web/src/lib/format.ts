export function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric" }).format(
    new Date(`${value}T00:00:00`),
  );
}

export function formatTime(value: string): string {
  const [hours, minutes] = value.split(":").map(Number);
  return new Intl.DateTimeFormat("en-IN", { hour: "numeric", minute: "2-digit" }).format(
    new Date(2026, 0, 1, hours, minutes),
  );
}

export function initials(name: string): string {
  return name.replace("Dr. ", "").split(" ").map((part) => part[0]).join("").slice(0, 2);
}

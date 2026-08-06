/** Joins class names, skipping falsy values. Small stand-in for `clsx`. */
export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

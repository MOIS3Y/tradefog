/** Both languages must expose the same keys and interpolation parameters. */
import { expect, it } from "vitest";
import { messages } from "@/i18n/messages";

type Dictionary = { readonly [key: string]: string | Dictionary };

/** Flatten namespaces without tying the check to a particular file layout. */
function flatten(dictionary: Dictionary, prefix = ""): Record<string, string> {
  const entries: Record<string, string> = {};
  for (const [key, value] of Object.entries(dictionary)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "string") entries[path] = value;
    else Object.assign(entries, flatten(value, path));
  }
  return entries;
}

/** Named and positional placeholders must agree, regardless of word order. */
function parameters(message: string): string[] {
  return [
    ...new Set([...message.matchAll(/\{(\w+)\}/g)].map((match) => match[1]!)),
  ].sort();
}

it("keeps translation keys and parameters aligned between languages", () => {
  const en = flatten(messages.en);
  const ru = flatten(messages.ru);
  expect(Object.keys(ru).sort()).toEqual(Object.keys(en).sort());
  for (const [key, value] of Object.entries(en)) {
    expect(parameters(ru[key]!), key).toEqual(parameters(value));
  }
});

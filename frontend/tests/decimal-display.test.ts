import { expect, it } from "vitest";
import { formatDecimal, formatAtrAmount } from "@/utils/decimal";

it.each([
  ["457.083528", "457.08"],
  ["1200.000000", "1200"],
  ["0.000012345678", "0.00001235"],
  ["0.000000000000000001", "0.000000000000000001"],
  ["0", "0"],
  [null, "—"],
  [undefined, "—"],
])("formats ATR amount %s as %s", (input, expected) => {
  expect(formatAtrAmount(input)).toBe(expected);
});

it.each([
  ["1E-8", "0.00000001"],
  ["1E-9", "0.000000001"],
  ["-1.2300e-8", "-0.0000000123"],
  ["1.2E+4", "12000"],
  ["0E-18", "0"],
  ["-0.000", "0"],
  ["0.10000", "0.1"],
  ["1.000000", "1"],
  ["3.000000", "3"],
  ["1.000000000000000000", "1"],
  ["0.000000000000000001", "0.000000000000000001"],
  ["0.125000", "0.125"],
  ["1234567890123456789.123456789E-2", "12345678901234567.89123456789"],
  ["invalid", "invalid"],
  ["1E-100000", "1E-100000"],
])("formats %s as an exact readable decimal", (input, expected) => {
  expect(formatDecimal(input)).toBe(expected);
});

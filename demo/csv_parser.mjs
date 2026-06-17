#!/usr/bin/env node
import { readFileSync, statSync } from "node:fs";

/**
 * Parse CSV text into an array of rows, where each row is an array of fields.
 *
 * Splitting rules (matching the outstanding expectations):
 *  - Content lines are separated by newlines.
 *  - A single trailing newline does not produce a spurious empty trailing row.
 *  - Empty input yields an empty array of rows.
 *  - Each line is split on commas; a line with K commas yields K+1 fields.
 *  - Rows are independent: no padding, truncation, or borrowing of fields.
 *
 * @param {string} text the raw file contents
 * @returns {string[][]} array of rows, each an array of field strings
 */
export function parseCsv(text) {
  if (text.length === 0) {
    return [];
  }
  // Normalise CRLF to LF so Windows line endings are handled, then split.
  const normalised = text.replace(/\r\n/g, "\n");
  // Drop exactly one trailing newline if present so "a,b\nc,d\n" => 2 rows.
  const trimmedOfTrailingNewline = normalised.endsWith("\n")
    ? normalised.slice(0, -1)
    : normalised;
  if (trimmedOfTrailingNewline.length === 0) {
    // Input was only a newline (or whitespace-only newline): no content lines.
    return [];
  }
  const lines = trimmedOfTrailingNewline.split("\n");
  return lines.map((line) => line.split(","));
}

/**
 * Read and parse a CSV file at the given path.
 * Throws on missing argument or unreadable / non-regular-file paths.
 *
 * @param {string|undefined} path
 * @returns {string[][]}
 */
export function parseCsvFile(path) {
  if (path === undefined || path === null || path === "") {
    throw new Error("Missing required argument: path to CSV file");
  }
  const stats = statSync(path); // throws if path does not exist
  if (!stats.isFile()) {
    throw new Error(`Not a regular file: ${path}`);
  }
  const text = readFileSync(path, "utf8"); // throws if unreadable
  return parseCsv(text);
}

// CLI entry point: run only when executed directly, not when imported.
const isMain =
  process.argv[1] &&
  import.meta.url === new URL(`file://${process.argv[1]}`).href;

if (isMain) {
  const path = process.argv[2];
  try {
    const rows = parseCsvFile(path);
    process.stdout.write(JSON.stringify(rows) + "\n");
    process.exit(0);
  } catch (err) {
    process.stderr.write(`Error: ${err.message}\n`);
    process.exit(1);
  }
}

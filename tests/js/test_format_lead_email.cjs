/**
 * Node unit tests for formatLeadEmail (Fase 8.3 / D11 revised).
 * Run: node tests/js/test_format_lead_email.cjs
 *
 * leads.js guards its DOM wiring behind `typeof document` and exposes
 * formatLeadEmail via module.exports, so it can be required here without a browser.
 */
const assert = require("assert");
const path = require("path");
const { formatLeadEmail } = require(path.join(__dirname, "..", "..", "frontend", "js", "leads.js"));

let passed = 0;
function test(name, fn) {
  fn();
  passed += 1;
  console.log(`  ok - ${name}`);
}

// 1. Text WITH \n is respected (no over-fragmentation: rules 1-5 skipped).
test("preserves existing newlines, does not over-fragment", () => {
  const out = formatLeadEmail("Hola,\n\nSoy Pame\nde Optimist");
  assert.strictEqual(out, "Hola,<br><br>Soy Pame<br>de Optimist");
});

// 2. Text WITHOUT \n falls back to the split heuristics.
test("no-newline fallback inserts breaks (period + uppercase)", () => {
  const out = formatLeadEmail("Hola muy bien.Soy Pame");
  assert.ok(out.includes(".<br><br>Soy"), `got: ${out}`);
});

// 3. Empty / null → null (caller shows the D7 fallback).
test("empty and null return null", () => {
  assert.strictEqual(formatLeadEmail(""), null);
  assert.strictEqual(formatLeadEmail(null), null);
  assert.strictEqual(formatLeadEmail(undefined), null);
});

// 4. *bold* → <strong>.
test("markdown bold becomes <strong>", () => {
  const out = formatLeadEmail("texto *negrita* fin");
  assert.ok(out.includes("<strong>negrita</strong>"), `got: ${out}`);
});

// 5. <script> is escaped, never emitted as a live tag.
test("script tag is escaped", () => {
  const out = formatLeadEmail("Hola <script>alert(1)</script> mundo");
  assert.ok(!out.includes("<script>"), `leaked tag: ${out}`);
  assert.ok(out.includes("&lt;script&gt;"), `got: ${out}`);
});

// 6. *<script>* → escaped first, then wrapped: <strong>&lt;script&gt;</strong> (inert).
test("bolded script payload is fully inert", () => {
  const out = formatLeadEmail("*<script>*");
  assert.strictEqual(out, "<strong>&lt;script&gt;</strong>");
  assert.ok(!out.includes("<script>"));
});

// 7. Emoji-only input does not crash and is returned intact.
test("emoji-only input is unchanged", () => {
  const out = formatLeadEmail("😀😀😀");
  assert.strictEqual(out, "😀😀😀");
});

// 8. Trailing newline does not produce spurious <br><br>.
test("trailing newline yields a single <br>", () => {
  assert.strictEqual(formatLeadEmail("Hola,\n"), "Hola,<br>");
});

// 9. Ampersand/angle escaping ordering is correct (& first).
test("ampersand is escaped before angle brackets", () => {
  assert.strictEqual(formatLeadEmail("a & b < c"), "a &amp; b &lt; c");
});

console.log(`\n${passed} formatLeadEmail tests passed`);
